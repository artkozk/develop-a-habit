from datetime import date

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import DayOffRule
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.calendar import _render_calendar, week_start
from develop_a_habit.handlers.export import export_diary_message, export_stats_html_message
from develop_a_habit.handlers.search_notes import show_search_menu
from develop_a_habit.handlers.stats import _render_stats
from develop_a_habit.services import build_services

router = Router(name="settings")

WEEKDAYS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}


def _settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Календарь", callback_data="settings:open:calendar")],
            [InlineKeyboardButton(text="🔎 Поиск заметок", callback_data="settings:open:search")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="settings:open:stats")],
            [InlineKeyboardButton(text="🗂 Экспорт дневника", callback_data="settings:open:export_diary")],
            [InlineKeyboardButton(text="📄 HTML статистика", callback_data="settings:open:export_stats_html")],
            [InlineKeyboardButton(text="🛌 Выходные дни", callback_data="settings:open:dayoff")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")],
        ]
    )


def _dayoff_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for weekday in range(7):
        marker = "✅ " if weekday in selected else ""
        row.append(
            InlineKeyboardButton(
                text=f"{marker}{WEEKDAYS[weekday]}",
                callback_data=f"settings:dayoff:toggle:{weekday}",
            )
        )
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="💾 Сохранить выходные", callback_data="settings:dayoff:save")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _selected_from_markup(markup: InlineKeyboardMarkup | None) -> set[int]:
    selected: set[int] = set()
    if markup is None:
        return selected

    for row in markup.inline_keyboard:
        for button in row:
            if button.callback_data and button.callback_data.startswith("settings:dayoff:toggle:"):
                if button.text.startswith("✅ "):
                    selected.add(int(button.callback_data.split(":")[-1]))
    return selected


async def _load_weekday_dayoffs(telegram_user_id: int) -> tuple[int, set[int]]:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        query = select(DayOffRule).where(DayOffRule.user_id == user.id, DayOffRule.weekday.is_not(None))
        rules = list(await session.scalars(query))
        selected = {rule.weekday for rule in rules if rule.weekday is not None}
        return user.id, selected


async def show_settings_menu(message: Message) -> None:
    await message.answer("Настройки и дополнительные разделы:", reply_markup=_settings_menu_keyboard())


async def _render_dayoff_editor(target: Message | CallbackQuery, telegram_user_id: int) -> None:
    _user_id, selected = await _load_weekday_dayoffs(telegram_user_id)
    text = "Выберите дни недели, которые считаются выходными:"
    keyboard = _dayoff_keyboard(selected)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "settings:menu")
async def settings_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Настройки и дополнительные разделы:",
        reply_markup=_settings_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("settings:open:"))
async def settings_open_section(callback: CallbackQuery) -> None:
    await callback.answer()
    section = callback.data.split(":")[-1]

    if section == "dayoff":
        await _render_dayoff_editor(callback, telegram_user_id=callback.from_user.id)
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
        await export_diary_message(callback.message)
        return

    if section == "export_stats_html":
        await export_stats_html_message(callback.message)
        return

    await callback.message.answer("Раздел не найден")


@router.callback_query(F.data.startswith("settings:dayoff:toggle:"))
async def settings_toggle_dayoff(callback: CallbackQuery) -> None:
    await callback.answer()
    weekday = int(callback.data.split(":")[-1])
    selected = _selected_from_markup(callback.message.reply_markup)

    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)

    await callback.message.edit_reply_markup(reply_markup=_dayoff_keyboard(selected))


@router.callback_query(F.data == "settings:dayoff:save")
async def settings_save_dayoff(callback: CallbackQuery) -> None:
    await callback.answer("Сохраняю...")
    settings = get_settings()
    selected = _selected_from_markup(callback.message.reply_markup)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        await services.habit_service.replace_day_off_weekdays(user.id, sorted(selected))

    await callback.message.answer("Настройки выходных обновлены ✅", reply_markup=_dayoff_keyboard(selected))
