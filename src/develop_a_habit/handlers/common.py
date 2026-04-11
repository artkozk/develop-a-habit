from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.domain.time_slots import resolve_slot_by_hour
from develop_a_habit.handlers.diary import show_diary_menu
from develop_a_habit.handlers.habits import _render_menu
from develop_a_habit.handlers.settings import show_settings_menu
from develop_a_habit.utils.telegram_safe import safe_edit_text

router = Router(name="common")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Привычки", callback_data="main:open:habits"),
                InlineKeyboardButton(text="Дневник", callback_data="main:open:diary"),
            ],
            [
                InlineKeyboardButton(text="Настройки", callback_data="main:open:settings"),
            ],
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


@router.callback_query(F.data == "main:menu")
async def main_menu_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await safe_edit_text(callback.message, "Главное меню", reply_markup=main_menu_keyboard())


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

    if section == "diary":
        await show_diary_menu(callback.message)
        return

    if section == "settings":
        await show_settings_menu(callback.message)
        return

    await callback.message.answer("Раздел не найден")
