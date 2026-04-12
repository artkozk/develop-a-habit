from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import CheckinStatus, Habit, HabitType, ScheduleType, TimeSlot
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.domain.schedule_engine import is_rule_due
from develop_a_habit.domain.sport_progress import compute_linear_target
from develop_a_habit.domain.time_slots import resolve_slot_by_hour
from develop_a_habit.handlers.states import HabitStates
from develop_a_habit.services import CheckinInput, HabitCreateInput, ScheduleRuleInput, build_services
from develop_a_habit.utils.telegram_safe import safe_edit_reply_markup, safe_edit_text

router = Router(name="habits")

SLOT_LABELS = {
    TimeSlot.MORNING: "🌅 Утро",
    TimeSlot.DAY: "☀️ День",
    TimeSlot.EVENING: "🌙 Вечер",
    TimeSlot.ALL_DAY: "🗓️ Весь день",
}

WEEKDAY_LABELS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}

DISPLAY_SLOT_ORDER = {
    TimeSlot.MORNING: 0,
    TimeSlot.DAY: 1,
    TimeSlot.ALL_DAY: 2,
    TimeSlot.EVENING: 3,
}


def _resolve_selected_slot(value: str | None) -> str:
    if value == "all":
        return "all"
    current_slot = resolve_slot_by_hour(datetime.now())
    return current_slot.value


def _habit_due_slots(habit: Habit, target_date: date) -> set[TimeSlot]:
    return {
        rule.time_slot
        for rule in habit.schedule_rules
        if is_rule_due(rule, target_date=target_date, slot=None)
    }


def _resolve_action_slot_for_habit(habit: Habit, selected_slot: str, target_date: date) -> TimeSlot:
    due_slots = _habit_due_slots(habit, target_date=target_date)
    current_slot = resolve_slot_by_hour(datetime.now())

    if selected_slot == "all":
        if due_slots:
            return sorted(due_slots, key=lambda slot: DISPLAY_SLOT_ORDER[slot])[0]
        if habit.schedule_rules:
            schedule_slots = {rule.time_slot for rule in habit.schedule_rules}
            return sorted(schedule_slots, key=lambda slot: DISPLAY_SLOT_ORDER[slot])[0]
        return current_slot

    selected = TimeSlot(selected_slot)
    if selected == TimeSlot.ALL_DAY:
        return TimeSlot.ALL_DAY
    if selected in due_slots:
        return selected
    if TimeSlot.ALL_DAY in due_slots:
        return TimeSlot.ALL_DAY
    return selected


def _habit_primary_slot_for_sort(habit: Habit) -> TimeSlot:
    if habit.schedule_rules:
        schedule_slots = {rule.time_slot for rule in habit.schedule_rules}
        return sorted(schedule_slots, key=lambda slot: DISPLAY_SLOT_ORDER[slot])[0]
    return TimeSlot.ALL_DAY


def _habit_created_sort_key(habit: Habit) -> tuple[datetime, int]:
    return (habit.created_at or datetime.min, habit.id)


def _sorted_habits_for_menu(
    habits: list[Habit],
    selected_slot: str,
    target_date: date,
    checkin_map: dict[tuple[int, str], CheckinStatus],
) -> list[tuple[Habit, TimeSlot, CheckinStatus | None]]:
    items: list[tuple[Habit, TimeSlot, CheckinStatus | None]] = []
    for habit in habits:
        action_slot = _resolve_action_slot_for_habit(
            habit=habit,
            selected_slot=selected_slot,
            target_date=target_date,
        )
        status = checkin_map.get((habit.id, action_slot.value))
        items.append((habit, action_slot, status))

    items.sort(
        key=lambda item: (
            DISPLAY_SLOT_ORDER[item[1]],
            *_habit_created_sort_key(item[0]),
        )
    )
    return items


def _sorted_habits_for_manage(habits: list[Habit]) -> list[Habit]:
    return sorted(
        habits,
        key=lambda habit: (
            DISPLAY_SLOT_ORDER[_habit_primary_slot_for_sort(habit)],
            *_habit_created_sort_key(habit),
        ),
    )


def _menu_keyboard(
    habits: list[Habit],
    selected_slot: str,
    view_mode: str,
    target_date: date,
    checkin_map: dict[tuple[int, str], CheckinStatus],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[_view_toggle_button(view_mode)]]

    for habit, action_slot, status in _sorted_habits_for_menu(
        habits=habits,
        selected_slot=selected_slot,
        target_date=target_date,
        checkin_map=checkin_map,
    ):
        marker = _status_marker(status, habit.habit_type)
        name = habit.name
        icon = _habit_emoji(habit)
        item_text = f"{marker} {name}" if not icon else f"{marker} {icon} {name}"
        sport_target = compute_linear_target(habit, target_date=target_date)
        if sport_target is not None:
            sets, reps = sport_target
            item_text = f"{item_text} [{sets}x{reps}]"
        rows.append(
            [
                InlineKeyboardButton(
                    text=item_text,
                    callback_data=f"habits:tap:{habit.id}:{action_slot.value}:{view_mode}",
                ),
            ]
        )

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _manage_keyboard(habits: list[Habit]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Добавить привычку", callback_data="habits:add")],
    ]

    for habit in _sorted_habits_for_manage(habits):
        icon = _habit_emoji(habit)
        habit_text = habit.name if not icon else f"{icon} {habit.name}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=habit_text,
                    callback_data=f"habits:edit:{habit.id}:manage",
                ),
                InlineKeyboardButton(text="🗑", callback_data=f"habits:delete:{habit.id}:manage"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎯 Настроить цель",
                    callback_data=f"habits:goalcfg:{habit.id}",
                )
            ]
        )
        if habit.is_sport:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🏋️ Настроить спорт-план",
                        callback_data=f"habits:sportcfg:{habit.id}",
                    )
                ]
            )

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _create_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Позитивная", callback_data="habits:add:type:positive"),
                InlineKeyboardButton(text="🚫 Негативная", callback_data="habits:add:type:negative"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")],
        ]
    )

def _status_marker(status: CheckinStatus | None, habit_type: HabitType) -> str:
    if status is None:
        if habit_type == HabitType.NEGATIVE:
            return "✅"
        return "▫️"
    if status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}:
        return "✅"
    if habit_type == HabitType.NEGATIVE and status == CheckinStatus.VIOLATED:
        return "❌"
    if status == CheckinStatus.MISSED:
        return "❌"
    return "▫️"


def _habit_emoji(habit: Habit) -> str:
    return habit.icon_emoji or ""


def _view_toggle_button(view_mode: str) -> InlineKeyboardButton:
    if view_mode == "all":
        return InlineKeyboardButton(text="↩️ Текущий период", callback_data="habits:menu:auto")
    return InlineKeyboardButton(text="📋 Показать все", callback_data="habits:menu:all")


def _goal_settings_keyboard(habit_id: int, goal_reached: bool) -> InlineKeyboardMarkup:
    extend_text = "🚀 Продлить цель" if goal_reached else "⏳ Продлить цель"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Установить/изменить цель", callback_data=f"habits:goalcfg:set:{habit_id}")],
            [InlineKeyboardButton(text=extend_text, callback_data=f"habits:goalcfg:extend:{habit_id}")],
            [InlineKeyboardButton(text="🧹 Сбросить цель", callback_data=f"habits:goalcfg:clear:{habit_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")],
        ]
    )


def _sport_adherence_keyboard(habit_id: int, slot: TimeSlot, view_mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, по плану",
                    callback_data=f"habits:sportadherence:{habit_id}:{slot.value}:{view_mode}:yes",
                ),
                InlineKeyboardButton(
                    text="❌ Нет, не по плану",
                    callback_data=f"habits:sportadherence:{habit_id}:{slot.value}:{view_mode}:no",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"habits:menu:{view_mode}")],
        ]
    )


def _sport_settings_keyboard(
    habit_id: int,
    progression_enabled: bool,
    preset: tuple[int, int] | None = None,
) -> InlineKeyboardMarkup:
    toggle_label = "🔁 Прогрессия: ВКЛ" if progression_enabled else "🔁 Прогрессия: ВЫКЛ"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🎯 Изменить базу (NxM)", callback_data=f"habits:sportcfg:base:{habit_id}")],
        [InlineKeyboardButton(text="📈 Изменить шаг (повт/нед)", callback_data=f"habits:sportcfg:step:{habit_id}")],
        [InlineKeyboardButton(text=toggle_label, callback_data=f"habits:sportcfg:toggle:{habit_id}")],
    ]
    if preset is not None:
        sets, reps = preset
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"⚡ Быстрый пресет {sets}x{reps}",
                    callback_data=f"habits:sportcfg:preset:{habit_id}:{sets}:{reps}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _recommended_sport_preset(habit_name: str) -> tuple[int, int] | None:
    value = habit_name.lower()
    if "подтяг" in value:
        return 2, 12
    if "отжим" in value:
        return 2, 15
    return None


def _normalize_slot_selection(slot_values: list[str] | None) -> list[TimeSlot]:
    selected: set[TimeSlot] = set()
    for value in slot_values or []:
        try:
            selected.add(TimeSlot(value))
        except ValueError:
            continue
    if TimeSlot.ALL_DAY in selected:
        return [TimeSlot.ALL_DAY]
    return sorted(selected, key=lambda slot: DISPLAY_SLOT_ORDER[slot])


def _create_slot_keyboard(selected: list[TimeSlot]) -> InlineKeyboardMarkup:
    selected_set = set(selected)

    def label(slot: TimeSlot) -> str:
        marker = "✅ " if slot in selected_set else ""
        return f"{marker}{SLOT_LABELS[slot]}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label(TimeSlot.MORNING), callback_data="habits:add:slot:toggle:morning")],
            [InlineKeyboardButton(text=label(TimeSlot.DAY), callback_data="habits:add:slot:toggle:day")],
            [InlineKeyboardButton(text=label(TimeSlot.EVENING), callback_data="habits:add:slot:toggle:evening")],
            [InlineKeyboardButton(text=label(TimeSlot.ALL_DAY), callback_data="habits:add:slot:toggle:all_day")],
            [InlineKeyboardButton(text="Готово", callback_data="habits:add:slot:done")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")],
        ]
    )


def _create_schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Каждый день", callback_data="habits:add:schedule:daily")],
            [InlineKeyboardButton(text="Через день", callback_data="habits:add:schedule:every_other_day")],
            [InlineKeyboardButton(text="Конкретные дни недели", callback_data="habits:add:schedule:specific_weekdays")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")],
        ]
    )


def _weekday_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    chunk: list[InlineKeyboardButton] = []
    for weekday in range(7):
        marker = "✅ " if weekday in selected else ""
        chunk.append(
            InlineKeyboardButton(
                text=f"{marker}{WEEKDAY_LABELS[weekday]}",
                callback_data=f"habits:add:weekday:{weekday}",
            )
        )
        if len(chunk) == 4:
            rows.append(chunk)
            chunk = []
    if chunk:
        rows.append(chunk)
    rows.append([InlineKeyboardButton(text="Готово", callback_data="habits:add:weekday:done")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _sport_toggle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏋️ Да", callback_data="habits:add:sport:yes"),
                InlineKeyboardButton(text="Нет", callback_data="habits:add:sport:no"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:manage")],
        ]
    )


def _input_back_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)],
        ]
    )


async def _render_menu(target: Message | CallbackQuery, telegram_user_id: int, selected_slot: str) -> None:
    settings = get_settings()
    view_mode = "all" if selected_slot == "all" else "auto"
    selected_slot = _resolve_selected_slot(selected_slot)
    used_fallback = False

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        target_date = date.today()

        if view_mode == "all":
            habits = await services.habit_service.list_habits(user.id)
        else:
            slot = TimeSlot(selected_slot)
            habits = await services.habit_service.list_due_habits(user.id, target_date=target_date, slot=slot)
            if not habits:
                # Fallback: current period is empty, so show all due habits for today.
                habits = await services.habit_service.list_due_habits(user.id, target_date=target_date, slot=None)
                used_fallback = True
        checkins = await services.habit_service.get_checkins_for_date(user_id=user.id, target_date=target_date)

    checkin_map = {(item.habit_id, item.time_slot.value): item.status for item in checkins}
    if view_mode == "all":
        title_slot = "все привычки"
        detail_line = "Тап по привычке: поставить/снять отметку."
    else:
        title_slot = f"текущий период: {SLOT_LABELS[TimeSlot(selected_slot)]}"
        detail_line = "Тап по привычке: поставить/снять отметку."
        if used_fallback:
            detail_line = "В текущем периоде пусто, показываю все привычки на сегодня."

    text = f"Привычки на сегодня ({title_slot}).\n{detail_line}"
    keyboard = _menu_keyboard(
        habits=habits,
        selected_slot=selected_slot,
        view_mode=view_mode,
        target_date=target_date,
        checkin_map=checkin_map,
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await safe_edit_text(target.message, text, reply_markup=keyboard)


async def show_habits_manage_menu(target: Message | CallbackQuery, telegram_user_id: int) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        habits = await services.habit_service.list_habits(user.id)

    text = "Управление привычками:"
    keyboard = _manage_keyboard(habits)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await safe_edit_text(target.message, text, reply_markup=keyboard)


async def _render_sport_config(
    target: Message | CallbackQuery,
    telegram_user_id: int,
    habit_id: int,
) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))

    if habit is None:
        if isinstance(target, Message):
            await target.answer("Привычка не найдена")
        else:
            await target.message.answer("Привычка не найдена")
        return

    if not habit.is_sport:
        if isinstance(target, Message):
            await target.answer("Это не спорт-привычка. Включите спорт-режим при создании.")
        else:
            await target.message.answer("Это не спорт-привычка. Включите спорт-режим при создании.")
        return

    today_target = compute_linear_target(habit, target_date=date.today())
    target_label = "не задана"
    if today_target is not None:
        target_label = f"{today_target[0]}x{today_target[1]}"

    base_label = (
        f"{habit.sport_base_sets}x{habit.sport_base_reps}"
        if habit.sport_base_sets is not None and habit.sport_base_reps is not None
        else "не задана"
    )
    step_label = habit.sport_linear_step_reps if habit.sport_linear_step_reps is not None else 0
    progress_label = "включена" if habit.sport_progression_enabled else "выключена"
    recommended = _recommended_sport_preset(habit.name)
    recommended_line = ""
    if recommended is not None:
        recommended_line = f"\nРекомендованный пресет: {recommended[0]}x{recommended[1]}"

    text = (
        f"🏋️ Настройки спорт-привычки\n"
        f"Привычка: {habit.name}\n\n"
        f"База: {base_label}\n"
        f"Шаг: +{step_label} повт/нед\n"
        f"Прогрессия: {progress_label}\n"
        f"Цель на сегодня: {target_label}"
        f"{recommended_line}"
    )
    keyboard = _sport_settings_keyboard(
        habit_id=habit.id,
        progression_enabled=habit.sport_progression_enabled,
        preset=recommended,
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await safe_edit_text(target.message, text, reply_markup=keyboard)


async def _render_goal_config(
    target: Message | CallbackQuery,
    telegram_user_id: int,
    habit_id: int,
) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        progress_items = await services.metrics_service.compute_habit_progress(
            user_id=user.id,
            start_date=date.today() - timedelta(days=6),
            end_date=date.today(),
            today=date.today(),
        )

    if habit is None:
        if isinstance(target, Message):
            await target.answer("Привычка не найдена")
        else:
            await target.message.answer("Привычка не найдена")
        return

    progress = next((item for item in progress_items if item.habit_id == habit.id), None)
    adherence_days_total = progress.adherence_days_total if progress is not None else 0
    current_streak_days = progress.current_streak_days if progress is not None else 0
    goal_progress_days = progress.goal_progress_days if progress is not None else 0
    goal_reached = progress.goal_reached if progress is not None else False

    goal_label = "не задана"
    if habit.goal_days is not None and habit.goal_days > 0:
        start = habit.goal_start_date.strftime("%d.%m.%Y") if habit.goal_start_date else "не задана"
        reached_marker = " ✅" if goal_reached else ""
        goal_label = f"{goal_progress_days}/{habit.goal_days} дней (старт {start}){reached_marker}"

    text = (
        f"🎯 Цель привычки\n"
        f"Привычка: {habit.name}\n\n"
        f"Держитесь: {current_streak_days} дн подряд\n"
        f"Всего дней соблюдения: {adherence_days_total}\n"
        f"Циклов цели завершено: {habit.goal_completed_cycles or 0}\n"
        f"Текущая цель: {goal_label}"
    )
    keyboard = _goal_settings_keyboard(habit.id, goal_reached=goal_reached)

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await safe_edit_text(target.message, text, reply_markup=keyboard)


def _build_rules_from_state(data: dict) -> tuple[list[ScheduleRuleInput], TimeSlot]:
    schedule_type = ScheduleType(data["schedule"])
    selected_slots = _normalize_slot_selection(data.get("slots"))
    if not selected_slots and data.get("slot"):
        # Backward compatibility for stale callback flows with single-slot payload.
        selected_slots = _normalize_slot_selection([data["slot"]])
    if not selected_slots:
        selected_slots = [TimeSlot.ALL_DAY]
    slot = selected_slots[0]
    rules: list[ScheduleRuleInput] = []

    if schedule_type == ScheduleType.SPECIFIC_WEEKDAYS:
        for weekday in data.get("weekdays", []):
            for each_slot in selected_slots:
                rules.append(
                    ScheduleRuleInput(
                        schedule_type=ScheduleType.SPECIFIC_WEEKDAYS,
                        time_slot=each_slot,
                        weekday=weekday,
                    )
                )
    elif schedule_type == ScheduleType.EVERY_OTHER_DAY:
        for each_slot in selected_slots:
            rules.append(
                ScheduleRuleInput(
                    schedule_type=ScheduleType.EVERY_OTHER_DAY,
                    time_slot=each_slot,
                    interval_days=2,
                    start_from=date.today(),
                )
            )
    else:
        for each_slot in selected_slots:
            rules.append(ScheduleRuleInput(schedule_type=ScheduleType.DAILY, time_slot=each_slot))

    return rules, slot


async def _save_new_habit_from_state(
    target: Message | CallbackQuery,
    state: FSMContext,
    telegram_user_id: int,
) -> None:
    data = await state.get_data()
    rules, _slot = _build_rules_from_state(data)
    payload = HabitCreateInput(
        name=data["name"],
        icon_emoji=data.get("icon_emoji"),
        habit_type=HabitType(data["habit_type"]),
        is_sport=bool(data.get("is_sport", False)),
        sport_base_sets=data.get("sport_base_sets"),
        sport_base_reps=data.get("sport_base_reps"),
        sport_linear_step_reps=data.get("sport_linear_step_reps"),
        sport_progression_enabled=bool(data.get("sport_progression_enabled", True)),
        sport_start_date=date.today() if data.get("is_sport") else None,
        schedule_rules=rules,
    )

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        await services.habit_service.create_habit(user.id, payload)

    await state.clear()
    if isinstance(target, CallbackQuery):
        await target.answer("Привычка добавлена ✅")
        await show_habits_manage_menu(target, telegram_user_id=telegram_user_id)
    else:
        await target.answer("Привычка добавлена ✅")
        await show_habits_manage_menu(target, telegram_user_id=telegram_user_id)


@router.callback_query(F.data == "habits:manage")
async def habits_manage(callback: CallbackQuery) -> None:
    await callback.answer()
    await show_habits_manage_menu(callback, telegram_user_id=callback.from_user.id)


@router.callback_query(F.data.startswith("habits:goalcfg:set:"))
async def habits_goalcfg_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(goalcfg_habit_id=habit_id)
    await state.set_state(HabitStates.waiting_goal_days)
    await safe_edit_text(
        callback.message,
        "Введите цель в днях (например: 30).",
        reply_markup=_input_back_keyboard(f"habits:goalcfg:{habit_id}"),
    )


@router.callback_query(F.data.startswith("habits:goalcfg:extend:"))
async def habits_goalcfg_extend(callback: CallbackQuery) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await safe_edit_text(
                callback.message,
                "Привычка не найдена.",
                reply_markup=_input_back_keyboard("habits:manage"),
            )
            return
        if habit.goal_days is None or habit.goal_days <= 0 or habit.goal_start_date is None:
            await safe_edit_text(
                callback.message,
                "Сначала установите цель в днях.",
                reply_markup=_input_back_keyboard(f"habits:goalcfg:{habit_id}"),
            )
            return

        progress_items = await services.metrics_service.compute_habit_progress(
            user_id=user.id,
            start_date=date.today() - timedelta(days=6),
            end_date=date.today(),
            today=date.today(),
        )
        progress = next((item for item in progress_items if item.habit_id == habit.id), None)
        if progress is None or not progress.goal_reached:
            await safe_edit_text(
                callback.message,
                "Цель еще не достигнута. Продолжайте текущий цикл.",
                reply_markup=_input_back_keyboard(f"habits:goalcfg:{habit_id}"),
            )
            return

        habit.goal_completed_cycles = (habit.goal_completed_cycles or 0) + 1
        habit.goal_start_date = date.today()
        await session.commit()

    await _render_goal_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:goalcfg:clear:"))
async def habits_goalcfg_clear(callback: CallbackQuery) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await safe_edit_text(
                callback.message,
                "Привычка не найдена.",
                reply_markup=_input_back_keyboard("habits:manage"),
            )
            return
        habit.goal_days = 30
        habit.goal_start_date = date.today()
        await session.commit()

    await _render_goal_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:goalcfg:"))
async def habits_goalcfg_open(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    habit_id = int(callback.data.split(":")[-1])
    await _render_goal_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:sportcfg:base:"))
async def habits_sportcfg_base_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(sportcfg_habit_id=habit_id)
    await state.set_state(HabitStates.waiting_sport_update_target)
    await safe_edit_text(
        callback.message,
        "Введите новый базовый план в формате NxM, например 2x12.",
        reply_markup=_input_back_keyboard(f"habits:sportcfg:{habit_id}"),
    )


@router.callback_query(F.data.startswith("habits:sportcfg:step:"))
async def habits_sportcfg_step_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(sportcfg_habit_id=habit_id)
    await state.set_state(HabitStates.waiting_sport_update_step)
    await safe_edit_text(
        callback.message,
        "Введите новый шаг прогрессии в повторах/неделю (целое число, например 1).",
        reply_markup=_input_back_keyboard(f"habits:sportcfg:{habit_id}"),
    )


@router.callback_query(F.data.startswith("habits:sportcfg:toggle:"))
async def habits_sportcfg_toggle(callback: CallbackQuery) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await safe_edit_text(
                callback.message,
                "Привычка не найдена.",
                reply_markup=_input_back_keyboard("habits:manage"),
            )
            return
        habit.sport_progression_enabled = not habit.sport_progression_enabled
        await session.commit()

    await _render_sport_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:sportcfg:preset:"))
async def habits_sportcfg_preset(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, _, habit_id_raw, sets_raw, reps_raw = callback.data.split(":")
    habit_id = int(habit_id_raw)
    sets = int(sets_raw)
    reps = int(reps_raw)

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await safe_edit_text(
                callback.message,
                "Привычка не найдена.",
                reply_markup=_input_back_keyboard("habits:manage"),
            )
            return

        habit.sport_base_sets = sets
        habit.sport_base_reps = reps
        habit.sport_start_date = date.today()
        await session.commit()

    await _render_sport_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:sportcfg:"))
async def habits_sportcfg_open(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    habit_id = int(callback.data.split(":")[-1])
    await _render_sport_config(callback, telegram_user_id=callback.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:menu"))
async def habits_menu_slot(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    selected_slot = _resolve_selected_slot(parts[2] if len(parts) > 2 else None)
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=selected_slot)


async def _save_checkin_for_user(
    telegram_user_id: int,
    habit_id: int,
    slot: TimeSlot,
    action: str,
    *,
    actual_sets: int | None = None,
    actual_reps_csv: str | None = None,
    target_sets: int | None = None,
    target_reps: int | None = None,
    sport_plan_adhered: bool | None = None,
) -> Habit | None:
    today = date.today()
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            return None

        if action == "done":
            new_status = CheckinStatus.DONE
        else:
            new_status = CheckinStatus.MISSED
            if habit.habit_type == HabitType.NEGATIVE:
                new_status = CheckinStatus.VIOLATED

        await services.habit_service.upsert_checkin(
            user_id=user.id,
            payload=CheckinInput(
                habit_id=habit_id,
                check_date=today,
                time_slot=slot,
                status=new_status.value,
                actual_sets=actual_sets,
                actual_reps_csv=actual_reps_csv,
                target_sets=target_sets,
                target_reps=target_reps,
                sport_plan_adhered=sport_plan_adhered,
            ),
        )
        return habit


@router.callback_query(F.data.startswith("habits:tap:"))
async def checkin_habit_tap(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    _, _, habit_id_value, slot_value, view_mode = callback.data.split(":")
    habit_id = int(habit_id_value)
    slot = TimeSlot(slot_value)

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        existing = await services.habit_service.get_checkin(
            user_id=user.id,
            habit_id=habit_id,
            check_date=date.today(),
            slot=slot,
        )

    if habit is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return

    if existing is not None:
        async with AsyncSessionFactory() as session:
            services = build_services(session)
            user = await services.user_service.get_or_create_by_telegram_id(
                telegram_user_id=callback.from_user.id,
                timezone=settings.timezone_default,
            )
            await services.habit_service.delete_checkin(
                user_id=user.id,
                habit_id=habit_id,
                check_date=date.today(),
                slot=slot,
            )
        await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=view_mode)
        return

    sport_target = compute_linear_target(habit, target_date=date.today())
    if habit.is_sport and sport_target is not None:
        target_sets, target_reps = sport_target
        await safe_edit_text(
            callback.message,
            (
                f"План для «{habit.name}»: {target_sets}x{target_reps}.\n"
                "Смогли придержаться плана прогрессии?"
            ),
            reply_markup=_sport_adherence_keyboard(
                habit_id=habit_id,
                slot=slot,
                view_mode=view_mode,
            ),
        )
        return

    action = "done"
    if habit.habit_type == HabitType.NEGATIVE:
        action = "fail"
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=habit_id,
        slot=slot,
        action=action,
    )
    if saved is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=view_mode)


@router.callback_query(F.data.startswith("habits:fail:"))
async def checkin_habit_fail(callback: CallbackQuery) -> None:
    _, _, habit_id_value, slot_value, selected_slot = callback.data.split(":")
    await callback.answer()
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action="fail",
    )
    if saved is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=_resolve_selected_slot(selected_slot))


@router.callback_query(F.data.startswith("habits:sportadherence:"))
async def checkin_sport_adherence(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, habit_id_value, slot_value, view_mode, decision = callback.data.split(":")
    habit_id = int(habit_id_value)
    slot = TimeSlot(slot_value)
    adhered = decision == "yes"

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))

    if habit is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return

    target_sets = None
    target_reps = None
    target = compute_linear_target(habit, target_date=date.today())
    if target is not None:
        target_sets, target_reps = target

    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=habit_id,
        slot=slot,
        action="done" if adhered else "fail",
        target_sets=target_sets,
        target_reps=target_reps,
        sport_plan_adhered=adhered,
    )
    if saved is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return
    await _render_menu(
        callback,
        telegram_user_id=callback.from_user.id,
        selected_slot=view_mode,
    )


@router.callback_query(F.data.startswith("habits:checkin:"))
async def checkin_habit_legacy(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Неверный формат", show_alert=True)
        return

    _, _, habit_id_value, slot_value, action = parts
    await callback.answer()
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action=action,
    )
    if saved is None:
        await safe_edit_text(
            callback.message,
            "Привычка не найдена.",
            reply_markup=_input_back_keyboard("main:menu"),
        )
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=_resolve_selected_slot(slot_value))


@router.callback_query(F.data == "habits:add")
async def add_habit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await safe_edit_text(
        callback.message,
        "Шаг 1/5. Выберите тип привычки:",
        reply_markup=_create_type_keyboard(),
    )


@router.callback_query(F.data.startswith("habits:add:type:"))
async def add_habit_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_type = callback.data.split(":")[-1]
    await state.update_data(habit_type=habit_type, slots=[])
    await safe_edit_text(
        callback.message,
        "Шаг 2/5. Выберите один или несколько слотов времени:",
        reply_markup=_create_slot_keyboard([]),
    )


@router.callback_query(F.data.startswith("habits:add:slot:toggle:"))
async def add_habit_slot_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    slot = TimeSlot(callback.data.split(":")[-1])
    data = await state.get_data()
    selected = set(_normalize_slot_selection(data.get("slots")))

    if slot == TimeSlot.ALL_DAY:
        selected = {TimeSlot.ALL_DAY}
    else:
        selected.discard(TimeSlot.ALL_DAY)
        if slot in selected:
            selected.remove(slot)
        else:
            selected.add(slot)

    normalized = _normalize_slot_selection([item.value for item in selected])
    await state.update_data(slots=[item.value for item in normalized])
    await safe_edit_reply_markup(callback.message, reply_markup=_create_slot_keyboard(normalized))


@router.callback_query(F.data == "habits:add:slot:done")
async def add_habit_slot_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    selected = _normalize_slot_selection(data.get("slots"))
    if not selected:
        await safe_edit_text(
            callback.message,
            "Шаг 2/5. Выберите хотя бы один слот времени:",
            reply_markup=_create_slot_keyboard([]),
        )
        return

    await safe_edit_text(
        callback.message,
        "Шаг 3/5. Выберите расписание:",
        reply_markup=_create_schedule_keyboard(),
    )


@router.callback_query(F.data.startswith("habits:add:slot:"))
async def add_habit_slot_legacy(callback: CallbackQuery, state: FSMContext) -> None:
    """Backward compatibility for stale single-slot callback buttons."""
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 4:
        return
    slot_value = parts[-1]
    try:
        slot = TimeSlot(slot_value)
    except ValueError:
        return
    await state.update_data(slots=[slot.value], slot=slot.value)
    await safe_edit_text(
        callback.message,
        "Шаг 3/5. Выберите расписание:",
        reply_markup=_create_schedule_keyboard(),
    )


@router.callback_query(F.data.startswith("habits:add:schedule:"))
async def add_habit_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    schedule = callback.data.split(":")[-1]
    await state.update_data(schedule=schedule)

    if schedule == "specific_weekdays":
        await state.update_data(weekdays=[])
        await safe_edit_text(
            callback.message,
            "Шаг 4/5. Выберите дни недели:",
            reply_markup=_weekday_keyboard(set()),
        )
    else:
        await state.set_state(HabitStates.waiting_name)
        await safe_edit_text(callback.message, "Шаг 4/5. Отправьте название привычки текстом.")


@router.callback_query(F.data.startswith("habits:add:weekday:"))
async def add_habit_weekdays(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    part = callback.data.split(":")[-1]
    data = await state.get_data()
    selected = set(data.get("weekdays", []))

    if part == "done":
        if not selected:
            await safe_edit_text(
                callback.message,
                "Выберите хотя бы 1 день недели.",
                reply_markup=_weekday_keyboard(selected),
            )
            return
        await state.update_data(weekdays=sorted(selected))
        await state.set_state(HabitStates.waiting_name)
        await safe_edit_text(callback.message, "Шаг 4/5. Отправьте название привычки текстом.")
        return

    weekday = int(part)
    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)

    await state.update_data(weekdays=sorted(selected))
    await safe_edit_reply_markup(callback.message, reply_markup=_weekday_keyboard(selected))


@router.message(HabitStates.waiting_name)
async def add_habit_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("Название не может быть пустым. Отправьте название еще раз.")
        return

    await state.update_data(name=name)
    await state.set_state(HabitStates.waiting_icon)
    await message.answer("Шаг 5/5. Отправьте эмодзи для привычки (или '-' чтобы пропустить).")


@router.message(HabitStates.waiting_icon)
async def add_habit_icon(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else ""
    icon = None
    if raw and raw != "-":
        icon = raw[0]

    await state.update_data(icon_emoji=icon)
    await message.answer("Это спортивная привычка с линейным ростом?", reply_markup=_sport_toggle_keyboard())


@router.callback_query(F.data.startswith("habits:add:sport:"))
async def add_habit_sport_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    mode = callback.data.split(":")[-1]
    if mode == "yes":
        await state.update_data(is_sport=True, sport_progression_enabled=True)
        await state.set_state(HabitStates.waiting_sport_target)
        await safe_edit_text(
            callback.message,
            "Введите базовый план в формате 3x8 (подходы x повторы).",
            reply_markup=_input_back_keyboard("habits:manage"),
        )
        return

    await state.update_data(
        is_sport=False,
        sport_base_sets=None,
        sport_base_reps=None,
        sport_linear_step_reps=None,
        sport_progression_enabled=False,
    )
    await _save_new_habit_from_state(
        callback,
        state,
        telegram_user_id=callback.from_user.id,
    )


@router.message(HabitStates.waiting_sport_target)
async def add_habit_sport_target(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").lower().replace(" ", "")
    if "x" not in raw:
        await message.answer("Неверный формат. Пример: 3x8")
        return

    sets_raw, reps_raw = raw.split("x", 1)
    if not sets_raw.isdigit() or not reps_raw.isdigit():
        await message.answer("Неверный формат. Используйте только числа, например: 3x8")
        return

    sets = int(sets_raw)
    reps = int(reps_raw)
    if sets <= 0 or reps <= 0:
        await message.answer("Подходы и повторы должны быть больше нуля.")
        return

    await state.update_data(sport_base_sets=sets, sport_base_reps=reps)
    await state.set_state(HabitStates.waiting_sport_step)
    await message.answer("Введите еженедельный шаг по повторам (целое число, например 1).")


@router.message(HabitStates.waiting_sport_step)
async def add_habit_sport_step(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите целое число шага, например 1")
        return

    step = int(raw)
    if step < 0:
        await message.answer("Шаг не может быть отрицательным.")
        return

    await state.update_data(sport_linear_step_reps=step, is_sport=True)
    await _save_new_habit_from_state(
        message,
        state,
        telegram_user_id=message.from_user.id,
    )


@router.message(HabitStates.waiting_sport_update_target)
async def update_habit_sport_target(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    habit_id = int(data.get("sportcfg_habit_id", 0))
    raw = (message.text or "").lower().replace(" ", "")
    if "x" not in raw:
        await message.answer("Неверный формат. Пример: 2x12")
        return

    sets_raw, reps_raw = raw.split("x", 1)
    if not sets_raw.isdigit() or not reps_raw.isdigit():
        await message.answer("Используйте только числа, например: 2x12")
        return

    sets = int(sets_raw)
    reps = int(reps_raw)
    if sets <= 0 or reps <= 0:
        await message.answer("Подходы и повторы должны быть больше нуля.")
        return

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await message.answer("Привычка не найдена.")
            await state.clear()
            return

        habit.sport_base_sets = sets
        habit.sport_base_reps = reps
        habit.sport_start_date = date.today()
        await session.commit()

    await state.clear()
    await message.answer("Базовый план обновлен ✅")
    await _render_sport_config(message, telegram_user_id=message.from_user.id, habit_id=habit_id)


@router.message(HabitStates.waiting_sport_update_step)
async def update_habit_sport_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    habit_id = int(data.get("sportcfg_habit_id", 0))
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите целое число, например 1")
        return

    step = int(raw)
    if step < 0:
        await message.answer("Шаг не может быть отрицательным.")
        return

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await message.answer("Привычка не найдена.")
            await state.clear()
            return

        habit.sport_linear_step_reps = step
        await session.commit()

    await state.clear()
    await message.answer("Шаг прогрессии обновлен ✅")
    await _render_sport_config(message, telegram_user_id=message.from_user.id, habit_id=habit_id)


@router.message(HabitStates.waiting_goal_days)
async def update_habit_goal_days(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    habit_id = int(data.get("goalcfg_habit_id", 0))
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите целое число дней, например: 30")
        return

    goal_days = int(raw)
    if goal_days <= 0:
        await message.answer("Цель должна быть больше 0 дней.")
        return

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await message.answer("Привычка не найдена.")
            await state.clear()
            return
        habit.goal_days = goal_days
        habit.goal_start_date = date.today()
        if habit.goal_completed_cycles is None:
            habit.goal_completed_cycles = 0
        await session.commit()

    await state.clear()
    await message.answer("Цель обновлена ✅")
    await _render_goal_config(message, telegram_user_id=message.from_user.id, habit_id=habit_id)


@router.callback_query(F.data.startswith("habits:delete:"))
async def delete_habit(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    habit_id = int(parts[2])
    context = parts[3] if len(parts) > 3 else "routine"

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        deleted = await services.habit_service.delete_habit(user.id, habit_id)

    if not deleted:
        await safe_edit_text(
            callback.message,
            "Не удалось удалить привычку.",
            reply_markup=_input_back_keyboard("habits:manage"),
        )
        return

    if context == "manage":
        await show_habits_manage_menu(callback, telegram_user_id=callback.from_user.id)
    else:
        await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot="auto")


@router.callback_query(F.data.startswith("habits:edit:"))
async def rename_habit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    habit_id = int(parts[2])
    context = parts[3] if len(parts) > 3 else "routine"
    await state.update_data(rename_habit_id=habit_id, rename_context=context)
    await state.set_state(HabitStates.waiting_rename)
    back_callback = "habits:manage" if context == "manage" else "habits:menu:auto"
    await safe_edit_text(
        callback.message,
        "Отправьте новое название привычки.",
        reply_markup=_input_back_keyboard(back_callback),
    )


@router.message(HabitStates.waiting_rename)
async def rename_habit_finish(message: Message, state: FSMContext) -> None:
    new_name = message.text.strip() if message.text else ""
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return

    data = await state.get_data()
    habit_id = int(data["rename_habit_id"])
    context = data.get("rename_context", "routine")

    async with AsyncSessionFactory() as session:
        user_id = await _resolve_user_id(session, message.from_user.id)
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id))
        if habit is None:
            await message.answer("Привычка не найдена.")
            await state.clear()
            return

        habit.name = new_name
        await session.commit()

    await state.clear()
    await message.answer("Название обновлено ✅")
    if context == "manage":
        await show_habits_manage_menu(message, telegram_user_id=message.from_user.id)
    else:
        await _render_menu(message, telegram_user_id=message.from_user.id, selected_slot="auto")


async def _resolve_user_id(session: AsyncSession, telegram_user_id: int) -> int:
    settings = get_settings()
    services = build_services(session)
    user = await services.user_service.get_or_create_by_telegram_id(
        telegram_user_id=telegram_user_id,
        timezone=settings.timezone_default,
    )
    return user.id
