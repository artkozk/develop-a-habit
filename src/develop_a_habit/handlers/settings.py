from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.calendar import _render_calendar, week_start
from develop_a_habit.handlers.export import export_diary_message, export_stats_html_message
from develop_a_habit.handlers.habits import show_habits_manage_menu
from develop_a_habit.handlers.search_notes import show_search_menu
from develop_a_habit.handlers.stats import _render_stats
from develop_a_habit.services import build_services
from develop_a_habit.utils.telegram_safe import safe_edit_text

router = Router(name="settings")

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _encode_day(day: date) -> str:
    return day.strftime("%Y%m%d")


def _decode_day(value: str) -> date:
    return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")


def _month_bounds(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    if start.month == 12:
        end = date(start.year, 12, 31)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


def _settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Управление привычками", callback_data="settings:open:habit_manage")],
            [InlineKeyboardButton(text="📅 Календарь", callback_data="settings:open:calendar")],
            [InlineKeyboardButton(text="🔎 Поиск заметок", callback_data="settings:open:search")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="settings:open:stats")],
            [InlineKeyboardButton(text="🗂 Экспорт дневника", callback_data="settings:open:export_diary")],
            [InlineKeyboardButton(text="📄 HTML статистика", callback_data="settings:open:export_stats_html")],
            [InlineKeyboardButton(text="🛌 Выходные по датам", callback_data="settings:dayoff:open")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")],
        ]
    )


async def _resolve_user_id(telegram_user_id: int) -> int:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        return user.id


def _dayoff_week_keyboard(anchor: date, selected: set[date]) -> InlineKeyboardMarkup:
    start = week_start(anchor)
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(7):
        day = start + timedelta(days=i)
        marker = "✅" if day in selected else "▫️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{WEEKDAYS[day.weekday()]} {day.strftime('%d.%m')} {marker}",
                    callback_data=f"settings:dayoff:toggle:week:{_encode_day(anchor)}:{_encode_day(day)}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="◀",
                callback_data=f"settings:dayoff:shift:week:{_encode_day(anchor)}:-1",
            ),
            InlineKeyboardButton(
                text="Месяц",
                callback_data=f"settings:dayoff:view:month:{_encode_day(anchor)}",
            ),
            InlineKeyboardButton(
                text="▶",
                callback_data=f"settings:dayoff:shift:week:{_encode_day(anchor)}:1",
            ),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dayoff_month_keyboard(anchor: date, selected: set[date]) -> InlineKeyboardMarkup:
    start, end = _month_bounds(anchor)
    rows: list[list[InlineKeyboardButton]] = []

    first_pad = start.weekday()
    days = [None] * first_pad + [start + timedelta(days=i) for i in range((end - start).days + 1)]

    for i in range(0, len(days), 7):
        chunk = days[i : i + 7]
        row: list[InlineKeyboardButton] = []
        for day in chunk:
            if day is None:
                row.append(InlineKeyboardButton(text=" ", callback_data="settings:noop"))
            else:
                marker = "✅" if day in selected else "▫️"
                row.append(
                    InlineKeyboardButton(
                        text=f"{day.day}{marker}",
                        callback_data=f"settings:dayoff:toggle:month:{_encode_day(anchor)}:{_encode_day(day)}",
                    )
                )
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="◀",
                callback_data=f"settings:dayoff:shift:month:{_encode_day(anchor)}:-1",
            ),
            InlineKeyboardButton(
                text="Неделя",
                callback_data=f"settings:dayoff:view:week:{_encode_day(anchor)}",
            ),
            InlineKeyboardButton(
                text="▶",
                callback_data=f"settings:dayoff:shift:month:{_encode_day(anchor)}:1",
            ),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _load_dayoff_dates(user_id: int, mode: str, anchor: date) -> tuple[date, date, set[date]]:
    if mode == "month":
        start, end = _month_bounds(anchor)
    else:
        start = week_start(anchor)
        end = start + timedelta(days=6)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        selected = await services.habit_service.list_day_off_dates(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )

    return start, end, selected


async def _render_dayoff_view(
    target: Message | CallbackQuery,
    telegram_user_id: int,
    mode: str,
    anchor: date,
) -> None:
    user_id = await _resolve_user_id(telegram_user_id)
    start, end, selected = await _load_dayoff_dates(user_id=user_id, mode=mode, anchor=anchor)

    if mode == "month":
        text = f"Выходные по датам (месяц): {start.strftime('%m.%Y')}\nТап по дню: включить/выключить."
        keyboard = _dayoff_month_keyboard(anchor=anchor, selected=selected)
    else:
        text = (
            f"Выходные по датам (неделя): {start.strftime('%d.%m')} - {end.strftime('%d.%m')}\n"
            "Тап по дню: включить/выключить."
        )
        keyboard = _dayoff_week_keyboard(anchor=anchor, selected=selected)

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await safe_edit_text(target.message, text, reply_markup=keyboard)


async def show_settings_menu(message: Message) -> None:
    await message.answer("Настройки и дополнительные разделы:", reply_markup=_settings_menu_keyboard())


@router.callback_query(F.data == "settings:noop")
async def settings_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "settings:menu")
async def settings_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await safe_edit_text(
        callback.message,
        "Настройки и дополнительные разделы:",
        reply_markup=_settings_menu_keyboard(),
    )


@router.callback_query(F.data == "settings:dayoff:open")
async def settings_dayoff_open(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_dayoff_view(
        callback,
        telegram_user_id=callback.from_user.id,
        mode="week",
        anchor=date.today(),
    )


@router.callback_query(F.data.startswith("settings:dayoff:view:"))
async def settings_dayoff_view(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, _, mode, anchor_raw = callback.data.split(":")
    anchor = _decode_day(anchor_raw)
    await _render_dayoff_view(
        callback,
        telegram_user_id=callback.from_user.id,
        mode=mode,
        anchor=anchor,
    )


@router.callback_query(F.data.startswith("settings:dayoff:shift:"))
async def settings_dayoff_shift(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, _, mode, anchor_raw, delta_raw = callback.data.split(":")
    anchor = _decode_day(anchor_raw)
    delta = int(delta_raw)

    if mode == "month":
        if delta > 0:
            if anchor.month == 12:
                anchor = date(anchor.year + 1, 1, 1)
            else:
                anchor = date(anchor.year, anchor.month + 1, 1)
        else:
            if anchor.month == 1:
                anchor = date(anchor.year - 1, 12, 1)
            else:
                anchor = date(anchor.year, anchor.month - 1, 1)
    else:
        anchor = anchor + timedelta(days=7 * delta)

    await _render_dayoff_view(
        callback,
        telegram_user_id=callback.from_user.id,
        mode=mode,
        anchor=anchor,
    )


@router.callback_query(F.data.startswith("settings:dayoff:toggle:"))
async def settings_dayoff_toggle(callback: CallbackQuery) -> None:
    await callback.answer("Обновляю...")
    _, _, _, mode, anchor_raw, target_raw = callback.data.split(":")
    anchor = _decode_day(anchor_raw)
    target = _decode_day(target_raw)
    user_id = await _resolve_user_id(callback.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        existing = await services.habit_service.list_day_off_dates(
            user_id=user_id,
            start_date=target,
            end_date=target,
        )
        if target in existing:
            await services.habit_service.remove_day_off_date(user_id=user_id, exact_date=target)
        else:
            await services.habit_service.add_day_off_date(user_id=user_id, exact_date=target)

    await _render_dayoff_view(
        callback,
        telegram_user_id=callback.from_user.id,
        mode=mode,
        anchor=anchor,
    )


@router.callback_query(F.data.startswith("settings:open:"))
async def settings_open_section(callback: CallbackQuery) -> None:
    await callback.answer()
    section = callback.data.split(":")[-1]

    if section == "habit_manage":
        await show_habits_manage_menu(callback, telegram_user_id=callback.from_user.id)
        return

    if section == "calendar":
        await _render_calendar(callback, telegram_user_id=callback.from_user.id, start=week_start(date.today()))
        return

    if section == "search":
        await show_search_menu(callback.message)
        return

    if section == "stats":
        await _render_stats(callback, telegram_user_id=callback.from_user.id, period="week")
        return

    if section == "export_diary":
        await export_diary_message(callback.message, telegram_user_id=callback.from_user.id)
        return

    if section == "export_stats_html":
        await export_stats_html_message(callback.message, telegram_user_id=callback.from_user.id)
        return

    await callback.message.answer("Раздел не найден")
