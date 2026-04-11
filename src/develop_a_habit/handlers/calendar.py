from collections import defaultdict
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import CheckinStatus, TimeSlot
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.domain.schedule_engine import is_rule_due
from develop_a_habit.services import build_services

router = Router(name="calendar")

WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def week_start(target: date) -> date:
    return target - timedelta(days=target.weekday())


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


async def _ensure_user_id(telegram_user_id: int) -> int:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        return user.id


async def _build_week_indicators(user_id: int, start: date) -> dict[date, str]:
    end = start + timedelta(days=6)
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        habits = await services.habit_service.list_habits(user_id=user_id, active_only=True)
        checkins = await services.habit_service.get_checkins_for_range(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )
        entries = await services.diary_service.list_entries_range(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )

    checkins_by_day: dict[date, dict[int, CheckinStatus]] = defaultdict(dict)
    for checkin in checkins:
        checkins_by_day[checkin.check_date][checkin.habit_id] = checkin.status

    note_days = {entry.entry_date for entry in entries}
    indicators: dict[date, str] = {}

    for day in (start + timedelta(days=i) for i in range(7)):
        due_habits = []
        for habit in habits:
            if any(is_rule_due(rule, day, slot=None) for rule in habit.schedule_rules):
                due_habits.append(habit)

        if not due_habits:
            indicators[day] = "▫️📝" if day in note_days else "▫️"
            continue

        done_count = 0
        fail_count = 0
        statuses = checkins_by_day.get(day, {})

        for habit in due_habits:
            status = statuses.get(habit.id)
            if status is None:
                continue
            if status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}:
                done_count += 1
            elif status in {CheckinStatus.MISSED, CheckinStatus.VIOLATED}:
                fail_count += 1

        if done_count == len(due_habits):
            base = "✅"
        elif done_count > 0 and fail_count == 0:
            base = "🟨"
        elif fail_count > 0:
            base = "❌"
        else:
            base = "▫️"

        indicators[day] = f"{base}📝" if day in note_days else base

    return indicators


async def _calendar_keyboard(user_id: int, start: date) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    week = [start + timedelta(days=i) for i in range(7)]
    indicators = await _build_week_indicators(user_id=user_id, start=start)

    row: list[InlineKeyboardButton] = []
    for day in week:
        row.append(
            InlineKeyboardButton(
                text=f"{WEEKDAY_SHORT[day.weekday()]} {day.day} {indicators[day]}",
                callback_data=f"calendar:day:{day.isoformat()}",
            )
        )
    rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Неделя", callback_data=f"calendar:shift:{start.isoformat()}:-1"),
            InlineKeyboardButton(text="➡️ Неделя", callback_data=f"calendar:shift:{start.isoformat()}:1"),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_calendar(target: Message | CallbackQuery, telegram_user_id: int, start: date) -> None:
    user_id = await _ensure_user_id(telegram_user_id)
    keyboard = await _calendar_keyboard(user_id=user_id, start=start)
    finish = start + timedelta(days=6)
    text = f"Календарь: {start.strftime('%d.%m.%Y')} - {finish.strftime('%d.%m.%Y')}"

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("calendar:shift:"))
async def calendar_shift(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, start_iso, shift_value = callback.data.split(":")
    current_start = parse_iso_date(start_iso)
    offset = int(shift_value)
    next_start = current_start + timedelta(days=7 * offset)
    await _render_calendar(callback, telegram_user_id=callback.from_user.id, start=next_start)


@router.callback_query(F.data.startswith("calendar:day:"))
async def calendar_day_details(callback: CallbackQuery) -> None:
    await callback.answer()
    day = parse_iso_date(callback.data.split(":")[-1])
    user_id = await _ensure_user_id(callback.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        habits = await services.habit_service.list_habits(user_id=user_id, active_only=True)
        due_habits = [
            habit for habit in habits if any(is_rule_due(rule, day, slot=None) for rule in habit.schedule_rules)
        ]
        checkins = await services.habit_service.get_checkins_for_date(user_id=user_id, target_date=day)
        entries = await services.diary_service.list_entries_for_date(user_id=user_id, entry_date=day)

    status_by_habit = {checkin.habit_id: checkin.status.value for checkin in checkins}
    lines = [f"День {day.strftime('%d.%m.%Y')}:"]
    if not due_habits:
        lines.append("- На этот день нет обязательных привычек")
    else:
        for habit in due_habits:
            status = status_by_habit.get(habit.id, "ожидает")
            lines.append(f"- {habit.name}: {status}")

    lines.append("")
    lines.append("Заметки:")
    if not entries:
        lines.append("- Нет заметок")
    else:
        for entry in entries:
            body = entry.text_body or "(без текста)"
            lines.append(f"- {body}")

    await callback.message.answer("\n".join(lines))
