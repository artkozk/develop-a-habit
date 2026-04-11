from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import DiaryEntryType
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.states import SearchStates
from develop_a_habit.services import build_services
from develop_a_habit.utils.telegram_safe import safe_edit_text

router = Router(name="search_notes")


def _search_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Все заметки", callback_data="search:mode:all")],
            [InlineKeyboardButton(text="🎤 Только голосовые", callback_data="search:mode:voice")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:menu")],
        ]
    )


async def show_search_menu(target: Message | CallbackQuery) -> None:
    if isinstance(target, Message):
        await target.answer("Выберите тип поиска заметок:", reply_markup=_search_menu_keyboard())
        return
    await safe_edit_text(
        target.message,
        "Выберите тип поиска заметок:",
        reply_markup=_search_menu_keyboard(),
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


@router.callback_query(F.data.startswith("search:mode:"))
async def search_mode(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    mode = callback.data.split(":")[-1]
    voice_only = mode == "voice"
    await state.update_data(search_voice_only=voice_only)
    await state.set_state(SearchStates.waiting_search_query)
    await safe_edit_text(
        callback.message,
        "Введите текст для поиска заметок.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="search:menu")],
            ]
        ),
    )


@router.callback_query(F.data == "search:menu")
async def search_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await show_search_menu(callback)


@router.message(SearchStates.waiting_search_query)
async def search_notes_run(message: Message, state: FSMContext) -> None:
    query_text = message.text.strip() if message.text else ""
    if not query_text:
        await message.answer("Введите непустой запрос.")
        return

    data = await state.get_data()
    voice_only = bool(data.get("search_voice_only", False))
    user_id = await _resolve_user_id(message.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        entries = await services.diary_service.search_entries(
            user_id=user_id,
            query_text=query_text,
            voice_only=voice_only,
            limit=20,
        )

        if not entries:
            await state.clear()
            await message.answer("Совпадений не найдено.", reply_markup=_search_menu_keyboard())
            return

        await message.answer(f"Найдено записей: {len(entries)}")
        for entry in entries:
            header = (
                f"Запись #{entry.id} | {entry.entry_date.strftime('%d.%m.%Y')} "
                f"| тип: {entry.entry_type.value}"
            )
            if entry.entry_type in {DiaryEntryType.TEXT, DiaryEntryType.MIXED} and entry.text_body:
                await message.answer(f"{header}\n{entry.text_body}")
            else:
                await message.answer(header)

            transcript = await services.diary_service.get_transcript_by_entry_id(entry.id)
            if transcript and transcript.transcript_text:
                await message.answer(f"Транскрипция: {transcript.transcript_text}")

            if entry.entry_type in {DiaryEntryType.VOICE, DiaryEntryType.MIXED}:
                voice = await services.diary_service.get_voice_by_entry_id(entry.id)
                if voice is not None:
                    await message.answer_voice(voice=voice.telegram_file_id)

    await state.clear()
    await message.answer("Поиск завершен", reply_markup=_search_menu_keyboard())
