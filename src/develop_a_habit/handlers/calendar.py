from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import CheckinStatus
from develop_a_habit.db.session import AsyncSessionFactory
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


async def _day_indicator(user_id: int, day: date) -> str:
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        due_habits = await services.habit_service.list_due_habits(user_id=user_id, target_date=day)
        if not due_habits:
            return "▫️"

        checkins = await services.habit_service.get_checkins_for_date(user_id=user_id, target_date=day)
        by_habit = {checkin.habit_id: checkin for checkin in checkins}

        done_count = 0
        fail_count = 0
        for habit in due_habits:
            checkin = by_habit.get(habit.id)
            if checkin is None:
                continue
            if checkin.status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}:
                done_count += 1
            elif checkin.status in {CheckinStatus.MISSED, CheckinStatus.VIOLATED}:
                fail_count += 1

        if done_count == len(due_habits):
            return "✅"
        if done_count > 0 and fail_count == 0:
            return "🟨"
        if fail_count > 0:
            return "❌"
        return "▫️"


async def _calendar_keyboard(user_id: int, start: date) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    week = [start + timedelta(days=i) for i in range(7)]

    row: list[InlineKeyboardButton] = []
    for day in week:
        indicator = await _day_indicator(user_id=user_id, day=day)
        row.append(
            InlineKeyboardButton(
                text=f"{WEEKDAY_SHORT[day.weekday()]} {day.day} {indicator}",
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
        await target.answer()


@router.message(Command("calendar"))
async def calendar_current_week(message: Message) -> None:
    start = week_start(date.today())
    await _render_calendar(message, telegram_user_id=message.from_user.id, start=start)


@router.callback_query(F.data.startswith("calendar:shift:"))
async def calendar_shift(callback: CallbackQuery) -> None:
    _, _, start_iso, shift_value = callback.data.split(":")
    current_start = parse_iso_date(start_iso)
    offset = int(shift_value)
    next_start = current_start + timedelta(days=7 * offset)
    await _render_calendar(callback, telegram_user_id=callback.from_user.id, start=next_start)


@router.callback_query(F.data.startswith("calendar:day:"))
async def calendar_day_details(callback: CallbackQuery) -> None:
    day = parse_iso_date(callback.data.split(":")[-1])
    user_id = await _ensure_user_id(callback.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        due_habits = await services.habit_service.list_due_habits(user_id=user_id, target_date=day)
        checkins = await services.habit_service.get_checkins_for_date(user_id=user_id, target_date=day)

    status_by_habit = {checkin.habit_id: checkin.status.value for checkin in checkins}
    lines = [f"День {day.strftime('%d.%m.%Y')}:"]
    if not due_habits:
        lines.append("- На этот день нет обязательных привычек")
    else:
        for habit in due_habits:
            status = status_by_habit.get(habit.id, "ожидает")
            lines.append(f"- {habit.name}: {status}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()
