from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.domain.time_slots import resolve_slot_by_hour
from develop_a_habit.handlers.calendar import _render_calendar, week_start
from develop_a_habit.handlers.diary import diary_menu as diary_menu_handler
from develop_a_habit.handlers.habits import _render_menu
from develop_a_habit.handlers.search_notes import search_notes_start
from develop_a_habit.handlers.settings import settings_menu
from develop_a_habit.handlers.stats import _render_stats

router = Router(name="common")


def _main_menu_keyboard() -> InlineKeyboardMarkup:
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
                InlineKeyboardButton(text="Поиск заметок", callback_data="main:open:search"),
                InlineKeyboardButton(text="Статистика", callback_data="main:open:stats"),
            ],
            [InlineKeyboardButton(text="Настройки", callback_data="main:open:settings")],
            [InlineKeyboardButton(text="Экспорт дневника", callback_data="main:open:export_diary")],
            [InlineKeyboardButton(text="HTML статистика", callback_data="main:open:export_stats_html")],
        ]
    )


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(
        "Привет! Develop A Habit запущен.\n"
        "Основной интерфейс доступен через кнопки ниже:",
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("main:open:"))
async def main_menu_open(callback: CallbackQuery) -> None:
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
        await callback.answer()
        await diary_menu_handler(callback.message)
        return

    if section == "search":
        await callback.answer()
        await search_notes_start(callback.message)
        return

    if section == "stats":
        await _render_stats(callback, telegram_user_id=callback.from_user.id, period="week")
        return

    if section == "settings":
        await callback.answer()
        await settings_menu(callback.message)
        return

    if section == "export_diary":
        await callback.answer()
        await callback.message.answer("Используйте команду /export_diary")
        return

    if section == "export_stats_html":
        await callback.answer()
        await callback.message.answer("Используйте команду /export_stats_html")
        return

    await callback.answer("Раздел не найден", show_alert=True)
