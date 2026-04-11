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
from develop_a_habit.domain.time_slots import resolve_slot_by_hour
from develop_a_habit.handlers.states import HabitStates
from develop_a_habit.services import CheckinInput, HabitCreateInput, ScheduleRuleInput, build_services

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

LAST_CHECKIN_SNAPSHOT: dict[int, dict[str, str | int | None]] = {}
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
        icon = "✅" if habit.habit_type == HabitType.POSITIVE else "🚫"
        marker = _status_marker(status, habit.habit_type)

        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker} {icon} {habit.name}",
                    callback_data=f"habits:tap:{habit.id}:{action_slot.value}:{selected_slot}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="❌",
                    callback_data=f"habits:fail:{habit.id}:{action_slot.value}:{selected_slot}",
                ),
                InlineKeyboardButton(text="✏️", callback_data=f"habits:edit:{habit.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"habits:delete:{habit.id}"),
            ]
        )

    rows.append([InlineKeyboardButton(text="↩️ Отмена последней отметки", callback_data="habits:undo")])
    rows.append([InlineKeyboardButton(text="➕ Добавить привычку", callback_data="habits:add")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _create_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Позитивная", callback_data="habits:add:type:positive"),
                InlineKeyboardButton(text="🚫 Негативная", callback_data="habits:add:type:negative"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:menu:all")],
        ]
    )


def _create_slot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌅 Утро", callback_data="habits:add:slot:morning")],
            [InlineKeyboardButton(text="☀️ День", callback_data="habits:add:slot:day")],
            [InlineKeyboardButton(text="🌙 Вечер", callback_data="habits:add:slot:evening")],
            [InlineKeyboardButton(text="🗓️ Весь день", callback_data="habits:add:slot:all_day")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:menu:all")],
        ]
    )


def _create_schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Каждый день", callback_data="habits:add:schedule:daily")],
            [InlineKeyboardButton(text="Через день", callback_data="habits:add:schedule:every_other_day")],
            [InlineKeyboardButton(text="Конкретные дни недели", callback_data="habits:add:schedule:specific_weekdays")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:menu:all")],
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
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="habits:menu:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _resolve_selected_slot(value: str | None) -> str:
    if value in {"morning", "day", "evening", "all_day", "all"}:
        return value
    current_slot = resolve_slot_by_hour(datetime.now())
    return current_slot.value


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
    text = f"Привычки на сегодня ({title_slot}).\nВыберите действие:"
    keyboard = _menu_keyboard(
        habits=habits,
        selected_slot=selected_slot,
        target_date=target_date,
        checkin_map=checkin_map,
    )

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("habits:menu"))
async def habits_menu_slot(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    selected_slot = _resolve_selected_slot(parts[2] if len(parts) > 2 else None)
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=selected_slot)


async def _apply_checkin(
    callback: CallbackQuery,
    habit_id: int,
    slot: TimeSlot,
    action: str,
    selected_slot: str,
) -> None:
    await callback.answer("Сохраняю...")
    today = date.today()

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        habit = await session.scalar(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
        if habit is None:
            await callback.message.answer("Привычка не найдена")
            return

        previous = await services.habit_service.get_checkin(
            user_id=user.id,
            habit_id=habit_id,
            check_date=today,
            slot=slot,
        )
        previous_status = previous.status.value if previous is not None else None

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
            ),
        )

        LAST_CHECKIN_SNAPSHOT[callback.from_user.id] = {
            "habit_id": habit_id,
            "slot": slot.value,
            "check_date": today.isoformat(),
            "previous_status": previous_status,
        }

    await _render_menu(
        callback,
        telegram_user_id=callback.from_user.id,
        selected_slot=_resolve_selected_slot(selected_slot),
    )


@router.callback_query(F.data.startswith("habits:tap:"))
async def checkin_habit_tap(callback: CallbackQuery) -> None:
    _, _, habit_id_value, slot_value, selected_slot = callback.data.split(":")
    await _apply_checkin(
        callback=callback,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action="done",
        selected_slot=selected_slot,
    )


@router.callback_query(F.data.startswith("habits:fail:"))
async def checkin_habit_fail(callback: CallbackQuery) -> None:
    _, _, habit_id_value, slot_value, selected_slot = callback.data.split(":")
    await _apply_checkin(
        callback=callback,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action="fail",
        selected_slot=selected_slot,
    )


@router.callback_query(F.data.startswith("habits:checkin:"))
async def checkin_habit_legacy(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Неверный формат", show_alert=True)
        return

    _, _, habit_id_value, slot_value, action = parts
    await _apply_checkin(
        callback=callback,
        habit_id=int(habit_id_value),
        slot=TimeSlot(slot_value),
        action=action,
        selected_slot=slot_value,
    )


@router.callback_query(F.data == "habits:undo")
async def undo_last_checkin(callback: CallbackQuery) -> None:
    await callback.answer()
    snapshot = LAST_CHECKIN_SNAPSHOT.get(callback.from_user.id)
    if snapshot is None:
        await callback.message.answer("Нет действий для отката")
        return

    habit_id = int(snapshot["habit_id"])
    slot = TimeSlot(str(snapshot["slot"]))
    target_date = date.fromisoformat(str(snapshot["check_date"]))
    previous_status = snapshot["previous_status"]

    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )

        if previous_status is None:
            await services.habit_service.delete_checkin(
                user_id=user.id,
                habit_id=habit_id,
                check_date=target_date,
                slot=slot,
            )
        else:
            await services.habit_service.upsert_checkin(
                user_id=user.id,
                payload=CheckinInput(
                    habit_id=habit_id,
                    check_date=target_date,
                    time_slot=slot,
                    status=str(previous_status),
                ),
            )

    LAST_CHECKIN_SNAPSHOT.pop(callback.from_user.id, None)
    await callback.message.answer("Последняя отметка отменена")
    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=slot.value)


@router.callback_query(F.data == "habits:add")
async def add_habit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Шаг 1/4. Выберите тип привычки:", reply_markup=_create_type_keyboard())


@router.callback_query(F.data.startswith("habits:add:type:"))
async def add_habit_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_type = callback.data.split(":")[-1]
    await state.update_data(habit_type=habit_type)
    await callback.message.edit_text("Шаг 2/4. Выберите слот времени:", reply_markup=_create_slot_keyboard())


@router.callback_query(F.data.startswith("habits:add:slot:"))
async def add_habit_slot(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    slot = callback.data.split(":")[-1]
    await state.update_data(slot=slot)
    await callback.message.edit_text("Шаг 3/4. Выберите расписание:", reply_markup=_create_schedule_keyboard())


@router.callback_query(F.data.startswith("habits:add:schedule:"))
async def add_habit_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    schedule = callback.data.split(":")[-1]
    await state.update_data(schedule=schedule)

    if schedule == "specific_weekdays":
        await state.update_data(weekdays=[])
        await callback.message.edit_text(
            "Шаг 4/4. Выберите дни недели:",
            reply_markup=_weekday_keyboard(set()),
        )
    else:
        await state.set_state(HabitStates.waiting_name)
        await callback.message.edit_text("Шаг 4/4. Отправьте название привычки текстом.")



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
        await callback.message.edit_text("Шаг 4/4. Отправьте название привычки текстом.")
        return

    weekday = int(part)
    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)

    await state.update_data(weekdays=sorted(selected))
    await callback.message.edit_reply_markup(reply_markup=_weekday_keyboard(selected))


@router.message(HabitStates.waiting_name)
async def add_habit_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("Название не может быть пустым. Отправьте название еще раз.")
        return

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

    payload = HabitCreateInput(
        name=name,
        habit_type=HabitType(data["habit_type"]),
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
    await _render_menu(message, telegram_user_id=message.from_user.id, selected_slot=slot.value)


@router.callback_query(F.data.startswith("habits:delete:"))
async def delete_habit(callback: CallbackQuery) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
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

    await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot="all")


@router.callback_query(F.data.startswith("habits:edit:"))
async def rename_habit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    habit_id = int(callback.data.split(":")[-1])
    await state.update_data(rename_habit_id=habit_id)
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
    await _render_menu(message, telegram_user_id=message.from_user.id, selected_slot="all")


async def _resolve_user_id(session: AsyncSession, telegram_user_id: int) -> int:
    settings = get_settings()
    services = build_services(session)
    user = await services.user_service.get_or_create_by_telegram_id(
        telegram_user_id=telegram_user_id,
        timezone=settings.timezone_default,
    )
    return user.id
