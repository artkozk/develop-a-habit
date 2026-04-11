from datetime import date, datetime

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

SLOT_BADGES = {
    TimeSlot.MORNING: "🌅",
    TimeSlot.DAY: "☀️",
    TimeSlot.EVENING: "🌙",
    TimeSlot.ALL_DAY: "🗓️",
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

SLOT_ORDER = {
    TimeSlot.MORNING: 0,
    TimeSlot.DAY: 1,
    TimeSlot.EVENING: 2,
    TimeSlot.ALL_DAY: 3,
}


def _slot_button(slot: TimeSlot, selected_slot: str) -> InlineKeyboardButton:
    marker = "•" if selected_slot == slot.value else ""
    return InlineKeyboardButton(
        text=f"{SLOT_LABELS[slot]} {marker}".strip(),
        callback_data=f"habits:menu:{slot.value}",
    )


def _resolve_selected_slot(value: str | None) -> str:
    if value in {"morning", "day", "evening", "all_day", "all"}:
        return value
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
        if TimeSlot.ALL_DAY in due_slots:
            return TimeSlot.ALL_DAY
        if current_slot in due_slots:
            return current_slot
        if due_slots:
            return sorted(due_slots, key=lambda slot: SLOT_ORDER[slot])[0]
        if habit.schedule_rules:
            return habit.schedule_rules[0].time_slot
        return current_slot

    selected = TimeSlot(selected_slot)
    if selected == TimeSlot.ALL_DAY:
        return TimeSlot.ALL_DAY
    if selected in due_slots:
        return selected
    if TimeSlot.ALL_DAY in due_slots:
        return TimeSlot.ALL_DAY
    return selected


def _status_marker(status: CheckinStatus | None, habit_type: HabitType) -> str:
    if status is None:
        return "▫️"
    if status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}:
        return "✅"
    if habit_type == HabitType.NEGATIVE and status == CheckinStatus.VIOLATED:
        return "❌"
    if status == CheckinStatus.MISSED:
        return "❌"
    return "▫️"


def _habit_emoji(habit: Habit) -> str:
    if habit.icon_emoji:
        return habit.icon_emoji
    return "✅" if habit.habit_type == HabitType.POSITIVE else "🚫"


def _menu_keyboard(
    habits: list[Habit],
    selected_slot: str,
    target_date: date,
    checkin_map: dict[tuple[int, str], CheckinStatus],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            _slot_button(TimeSlot.MORNING, selected_slot),
            _slot_button(TimeSlot.DAY, selected_slot),
            _slot_button(TimeSlot.EVENING, selected_slot),
        ],
        [
            _slot_button(TimeSlot.ALL_DAY, selected_slot),
            InlineKeyboardButton(text="📋 Все", callback_data="habits:menu:all"),
        ],
    ]

    for habit in habits:
        action_slot = _resolve_action_slot_for_habit(
            habit=habit,
            selected_slot=selected_slot,
            target_date=target_date,
        )
        status = checkin_map.get((habit.id, action_slot.value))
        marker = _status_marker(status, habit.habit_type)
        item_text = f"{marker} {SLOT_BADGES[action_slot]} {_habit_emoji(habit)} {habit.name}"
        sport_target = compute_linear_target(habit, target_date=target_date)
        if sport_target is not None:
            sets, reps = sport_target
            item_text = f"{item_text} [{sets}x{reps}]"
        rows.append(
            [
                InlineKeyboardButton(
                    text=item_text,
                    callback_data=f"habits:tap:{habit.id}:{action_slot.value}:{selected_slot}",
                ),
                InlineKeyboardButton(
                    text="❌",
                    callback_data=f"habits:fail:{habit.id}:{action_slot.value}:{selected_slot}",
                ),
            ]
        )

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _manage_keyboard(habits: list[Habit]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Добавить привычку", callback_data="habits:add")],
    ]

    for habit in habits:
        first_slot = habit.schedule_rules[0].time_slot if habit.schedule_rules else TimeSlot.DAY
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{SLOT_BADGES[first_slot]} {_habit_emoji(habit)} {habit.name}",
                    callback_data=f"habits:edit:{habit.id}:manage",
                ),
                InlineKeyboardButton(text="🗑", callback_data=f"habits:delete:{habit.id}:manage"),
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


def _create_slot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌅 Утро", callback_data="habits:add:slot:morning")],
            [InlineKeyboardButton(text="☀️ День", callback_data="habits:add:slot:day")],
            [InlineKeyboardButton(text="🌙 Вечер", callback_data="habits:add:slot:evening")],
            [InlineKeyboardButton(text="🗓️ Весь день", callback_data="habits:add:slot:all_day")],
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


async def _render_menu(target: Message | CallbackQuery, telegram_user_id: int, selected_slot: str) -> None:
    settings = get_settings()
    selected_slot = _resolve_selected_slot(selected_slot)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        target_date = date.today()

        if selected_slot == "all":
            habits = await services.habit_service.list_habits(user.id)
        else:
            slot = TimeSlot(selected_slot)
            habits = await services.habit_service.list_due_habits(user.id, target_date=target_date, slot=slot)
        checkins = await services.habit_service.get_checkins_for_date(user_id=user.id, target_date=target_date)

    checkin_map = {(item.habit_id, item.time_slot.value): item.status for item in checkins}
    title_slot = "все привычки" if selected_slot == "all" else f"слот: {SLOT_LABELS[TimeSlot(selected_slot)]}"
    text = f"Привычки на сегодня ({title_slot})."
    keyboard = _menu_keyboard(
        habits=habits,
        selected_slot=selected_slot,
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


def _build_rules_from_state(data: dict) -> tuple[list[ScheduleRuleInput], TimeSlot]:
    schedule_type = ScheduleType(data["schedule"])
    slot = TimeSlot(data["slot"])
    rules: list[ScheduleRuleInput] = []

    if schedule_type == ScheduleType.SPECIFIC_WEEKDAYS:
        for weekday in data.get("weekdays", []):
            rules.append(
                ScheduleRuleInput(
                    schedule_type=ScheduleType.SPECIFIC_WEEKDAYS,
                    time_slot=slot,
                    weekday=weekday,
                )
            )
    elif schedule_type == ScheduleType.EVERY_OTHER_DAY:
        rules.append(
            ScheduleRuleInput(
                schedule_type=ScheduleType.EVERY_OTHER_DAY,
                time_slot=slot,
                interval_days=2,
                start_from=date.today(),
            )
        )
    else:
        rules.append(ScheduleRuleInput(schedule_type=ScheduleType.DAILY, time_slot=slot))

    return rules, slot


async def _save_new_habit_from_state(message: Message, state: FSMContext) -> None:
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
        sport_start_date=date.today() if data.get("is_sport") else None,
        schedule_rules=rules,
    )

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        await services.habit_service.create_habit(user.id, payload)

    await state.clear()
    await message.answer("Привычка добавлена ✅")
    await show_habits_manage_menu(message, telegram_user_id=message.from_user.id)


@router.callback_query(F.data == "habits:manage")
async def habits_manage(callback: CallbackQuery) -> None:
    await callback.answer()
    await show_habits_manage_menu(callback, telegram_user_id=callback.from_user.id)


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
            ),
        )
        return habit


@router.callback_query(F.data.startswith("habits:tap:"))
async def checkin_habit_tap(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, habit_id_value, slot_value, selected_slot = callback.data.split(":")
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

    if habit is None:
        await callback.answer("Привычка не найдена", show_alert=True)
        return

    sport_target = compute_linear_target(habit, target_date=date.today())
    if habit.is_sport and sport_target is not None:
        target_sets, target_reps = sport_target
        await callback.answer()
        await state.update_data(
            sport_checkin_habit_id=habit_id,
            sport_checkin_slot=slot.value,
            sport_checkin_selected_slot=selected_slot,
            sport_checkin_target_sets=target_sets,
            sport_checkin_target_reps=target_reps,
        )
        await state.set_state(HabitStates.waiting_sport_result)
        await callback.message.answer(
            f"План {target_sets}x{target_reps}. Введите факт по подходам через запятую, например: 10,10,8"
        )
        return

    await callback.answer("Сохраняю...")
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=habit_id,
        slot=slot,
        action="done",
    )
    if saved is None:
        await callback.message.answer("Привычка не найдена")
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=_resolve_selected_slot(selected_slot))


@router.callback_query(F.data.startswith("habits:fail:"))
async def checkin_habit_fail(callback: CallbackQuery) -> None:
    _, _, habit_id_value, slot_value, selected_slot = callback.data.split(":")
    await callback.answer("Сохраняю...")
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action="fail",
    )
    if saved is None:
        await callback.message.answer("Привычка не найдена")
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=_resolve_selected_slot(selected_slot))


@router.callback_query(F.data.startswith("habits:checkin:"))
async def checkin_habit_legacy(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Неверный формат", show_alert=True)
        return

    _, _, habit_id_value, slot_value, action = parts
    await callback.answer("Сохраняю...")
    saved = await _save_checkin_for_user(
        telegram_user_id=callback.from_user.id,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action=action,
    )
    if saved is None:
        await callback.message.answer("Привычка не найдена")
        return
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=_resolve_selected_slot(slot_value))


@router.message(HabitStates.waiting_sport_result)
async def checkin_sport_result(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Введите повторы по подходам, например: 10,10,8")
        return

    parts = [piece.strip() for piece in raw.replace(";", ",").split(",") if piece.strip()]
    if not parts:
        await message.answer("Не понял формат. Пример: 10,10,8")
        return

    reps: list[int] = []
    for part in parts:
        if not part.isdigit():
            await message.answer("Только числа через запятую. Пример: 10,10,8")
            return
        reps.append(int(part))

    habit_id = int(data["sport_checkin_habit_id"])
    slot = TimeSlot(data["sport_checkin_slot"])
    selected_slot = data["sport_checkin_selected_slot"]
    target_sets = int(data["sport_checkin_target_sets"])
    target_reps = int(data["sport_checkin_target_reps"])

    saved = await _save_checkin_for_user(
        telegram_user_id=message.from_user.id,
        habit_id=habit_id,
        slot=slot,
        action="done",
        actual_sets=len(reps),
        actual_reps_csv=",".join(str(item) for item in reps),
        target_sets=target_sets,
        target_reps=target_reps,
    )
    if saved is None:
        await message.answer("Привычка не найдена")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"Зафиксировано: {len(reps)} подходов ({', '.join(str(item) for item in reps)})."
    )
    await _render_menu(message, telegram_user_id=message.from_user.id, selected_slot=_resolve_selected_slot(selected_slot))


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
    await state.update_data(habit_type=habit_type)
    await safe_edit_text(
        callback.message,
        "Шаг 2/5. Выберите слот времени:",
        reply_markup=_create_slot_keyboard(),
    )


@router.callback_query(F.data.startswith("habits:add:slot:"))
async def add_habit_slot(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    slot = callback.data.split(":")[-1]
    await state.update_data(slot=slot)
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
            await callback.message.answer("Выберите хотя бы 1 день")
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
        await state.update_data(is_sport=True)
        await state.set_state(HabitStates.waiting_sport_target)
        await callback.message.answer("Введите базовый план в формате 3x8 (подходы x повторы).")
        return

    await state.update_data(
        is_sport=False,
        sport_base_sets=None,
        sport_base_reps=None,
        sport_linear_step_reps=None,
    )
    await _save_new_habit_from_state(callback.message, state)


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
    await _save_new_habit_from_state(message, state)


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

    if deleted:
        await callback.message.answer("Привычка удалена")
    else:
        await callback.message.answer("Не удалось удалить привычку")

    if context == "manage":
        await show_habits_manage_menu(callback, telegram_user_id=callback.from_user.id)
    else:
        await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot="all")


@router.callback_query(F.data.startswith("habits:edit:"))
async def rename_habit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    habit_id = int(parts[2])
    context = parts[3] if len(parts) > 3 else "routine"
    await state.update_data(rename_habit_id=habit_id, rename_context=context)
    await state.set_state(HabitStates.waiting_rename)
    await callback.message.answer("Отправьте новое название привычки.")


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
        await _render_menu(message, telegram_user_id=message.from_user.id, selected_slot="all")


async def _resolve_user_id(session: AsyncSession, telegram_user_id: int) -> int:
    settings = get_settings()
    services = build_services(session)
    user = await services.user_service.get_or_create_by_telegram_id(
        telegram_user_id=telegram_user_id,
        timezone=settings.timezone_default,
    )
    return user.id
