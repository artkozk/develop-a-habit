from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.states import DiaryStates
from develop_a_habit.services import build_services

router = Router(name="diary")


def _diary_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Добавить запись", callback_data="diary:add_text")],
            [InlineKeyboardButton(text="📅 Записи за сегодня", callback_data="diary:list:today")],
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


@router.message(Command("diary"))
async def diary_menu(message: Message) -> None:
    await message.answer("Дневник: выберите действие", reply_markup=_diary_menu_keyboard())


@router.callback_query(F.data == "diary:add_text")
async def diary_add_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryStates.waiting_diary_text)
    await callback.message.answer("Отправьте текст записи дневника.")
    await callback.answer()


@router.message(DiaryStates.waiting_diary_text)
async def diary_add_text_finish(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer("Текст пустой, отправьте запись еще раз.")
        return

    user_id = await _resolve_user_id(message.from_user.id)
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        await services.diary_service.create_text_entry(
            user_id=user_id,
            entry_date=date.today(),
            text=text,
        )

    await state.clear()
    await message.answer("Запись сохранена ✅", reply_markup=_diary_menu_keyboard())


@router.callback_query(F.data.startswith("diary:list:"))
async def diary_list(callback: CallbackQuery) -> None:
    mode = callback.data.split(":")[-1]
    target_date = date.today() if mode == "today" else date.fromisoformat(mode)
    user_id = await _resolve_user_id(callback.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        entries = await services.diary_service.list_entries_for_date(user_id=user_id, entry_date=target_date)

    if not entries:
        await callback.message.answer(f"За {target_date.strftime('%d.%m.%Y')} заметок нет.")
        await callback.answer()
        return

    lines = [f"Заметки за {target_date.strftime('%d.%m.%Y')}:\n"]
    for index, entry in enumerate(entries, start=1):
        body = entry.text_body or "(без текста)"
        lines.append(f"{index}. {body}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()
