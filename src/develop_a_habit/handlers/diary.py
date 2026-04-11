from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import DiaryEntryType
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.states import DiaryStates
from develop_a_habit.jobs.transcription_queue import enqueue_transcription
from develop_a_habit.services import build_services

router = Router(name="diary")


def _diary_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Добавить запись", callback_data="diary:add_text")],
            [InlineKeyboardButton(text="🎤 Добавить голосовую", callback_data="diary:add_voice")],
            [InlineKeyboardButton(text="📅 Записи за сегодня", callback_data="diary:list:today")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:menu")],
        ]
    )


async def show_diary_menu(message: Message) -> None:
    await message.answer("Дневник: выберите действие", reply_markup=_diary_menu_keyboard())


async def _resolve_user_id(telegram_user_id: int) -> int:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        return user.id


@router.callback_query(F.data == "diary:add_text")
async def diary_add_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(DiaryStates.waiting_diary_text)
    await callback.message.answer("Отправьте текст записи дневника.")


@router.callback_query(F.data == "diary:add_voice")
async def diary_add_voice_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(DiaryStates.waiting_diary_voice)
    await callback.message.answer("Отправьте голосовое сообщение для дневника.")


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


@router.message(DiaryStates.waiting_diary_voice, F.voice)
async def diary_add_voice_finish(message: Message, state: FSMContext) -> None:
    voice = message.voice
    user_id = await _resolve_user_id(message.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        entry = await services.diary_service.create_voice_entry(
            user_id=user_id,
            entry_date=date.today(),
            telegram_file_id=voice.file_id,
            telegram_file_unique_id=voice.file_unique_id,
            duration_sec=voice.duration,
            mime=voice.mime_type,
            message_id=message.message_id,
        )
    await enqueue_transcription(entry_id=entry.id, telegram_file_id=voice.file_id)

    await state.clear()
    await message.answer(
        "Голосовая запись сохранена ✅ Транскрибация добавлена в очередь и появится чуть позже.",
        reply_markup=_diary_menu_keyboard(),
    )


@router.message(DiaryStates.waiting_diary_voice)
async def diary_add_voice_wrong_type(message: Message) -> None:
    await message.answer("Ожидаю голосовое сообщение (ГС).")


@router.callback_query(F.data.startswith("diary:list:"))
async def diary_list(callback: CallbackQuery) -> None:
    await callback.answer()
    mode = callback.data.split(":")[-1]
    target_date = date.today() if mode == "today" else date.fromisoformat(mode)
    user_id = await _resolve_user_id(callback.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        entries = await services.diary_service.list_entries_for_date(user_id=user_id, entry_date=target_date)

    if not entries:
        await callback.message.answer(f"За {target_date.strftime('%d.%m.%Y')} заметок нет.")
        return

    lines = [f"Заметки за {target_date.strftime('%d.%m.%Y')}:\n"]
    for index, entry in enumerate(entries, start=1):
        if entry.entry_type == DiaryEntryType.TEXT:
            body = entry.text_body or "(без текста)"
            lines.append(f"{index}. 📝 {body}")
        elif entry.entry_type == DiaryEntryType.VOICE:
            lines.append(f"{index}. 🎤 Голосовая заметка (ID: {entry.id})")
        else:
            body = entry.text_body or "(без текста)"
            lines.append(f"{index}. 📝🎤 {body}")

    await callback.message.answer("\n".join(lines), reply_markup=_diary_menu_keyboard())

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        for entry in entries:
            if entry.entry_type not in {DiaryEntryType.VOICE, DiaryEntryType.MIXED}:
                continue
            voice = await services.diary_service.get_voice_by_entry_id(entry.id)
            if voice is not None:
                await callback.message.answer_voice(
                    voice=voice.telegram_file_id,
                    caption=f"🎧 Голосовая заметка #{entry.id}",
                )
