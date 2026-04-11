from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.domain.time_slots import resolve_slot_by_hour
from develop_a_habit.handlers.calendar import _render_calendar, week_start
from develop_a_habit.handlers.diary import show_diary_menu
from develop_a_habit.handlers.export import export_diary_message, export_stats_html_message
from develop_a_habit.handlers.habits import _render_menu
from develop_a_habit.handlers.search_notes import show_search_menu
from develop_a_habit.handlers.settings import show_settings_menu
from develop_a_habit.handlers.stats import _render_stats

router = Router(name="common")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="main:open:today"),
                InlineKeyboardButton(text="Привычки", callback_data="main:open:habits"),
            ],
            [
                InlineKeyboardButton(text="Календарь", callback_data="main:open:calendar"),
                InlineKeyboardButton(text="Дневник", callback_data="main:open:diary"),
            ],
            [
                InlineKeyboardButton(text="Аналитика", callback_data="main:submenu:analytics"),
                InlineKeyboardButton(text="Еще", callback_data="main:submenu:more"),
            ],
        ]
    )


def analytics_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data="main:open:stats")],
            [InlineKeyboardButton(text="HTML статистика", callback_data="main:open:export_stats_html")],
            [InlineKeyboardButton(text="Экспорт дневника", callback_data="main:open:export_diary")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:submenu:root")],
        ]
    )


def more_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поиск заметок", callback_data="main:open:search")],
            [InlineKeyboardButton(text="Настройки", callback_data="main:open:settings")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:submenu:root")],
        ]
    )


async def show_main_menu(message: Message, text: str | None = None) -> None:
    await message.answer(
        text or "Главное меню",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(None), F.text)
async def open_menu_from_text(message: Message) -> None:
    await show_main_menu(message, text="Главное меню")


@router.callback_query(F.data.startswith("main:submenu:"))
async def main_submenu(callback: CallbackQuery) -> None:
    await callback.answer()
    submenu = callback.data.split(":")[-1]

    if submenu == "analytics":
        await callback.message.edit_text("Аналитика", reply_markup=analytics_menu_keyboard())
        return

    if submenu == "more":
        await callback.message.edit_text("Дополнительно", reply_markup=more_menu_keyboard())
        return

    await callback.message.edit_text("Главное меню", reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("main:open:"))
async def main_menu_open(callback: CallbackQuery) -> None:
    await callback.answer()
    section = callback.data.split(":")[-1]

    if section == "today":
        current_slot = resolve_slot_by_hour(datetime.now()).value
        await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot=current_slot)
        return

    if section == "habits":
        await _render_menu(callback, telegram_user_id=callback.from_user.id, selected_slot="")
        return

    if section == "calendar":
        await _render_calendar(callback, telegram_user_id=callback.from_user.id, start=week_start(date.today()))
        return

    if section == "diary":
        await show_diary_menu(callback.message)
        return

    if section == "search":
        await show_search_menu(callback.message)
        return

    if section == "stats":
        await _render_stats(callback, telegram_user_id=callback.from_user.id, period="week")
        return

    if section == "settings":
        await show_settings_menu(callback.message)
        return

    if section == "export_diary":
        await export_diary_message(callback.message)
        return

    if section == "export_stats_html":
        await export_stats_html_message(callback.message)
        return

    await callback.message.answer("Раздел не найден")
