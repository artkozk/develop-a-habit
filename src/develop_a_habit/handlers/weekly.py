from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import WeeklyPrompt
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.handlers.states import WeeklyStates
from develop_a_habit.services import build_services, create_transcription_service

router = Router(name="weekly")


def _decode_day(value: str) -> date:
    return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")


async def _resolve_user_id(telegram_user_id: int) -> int:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        return user.id


async def _mark_weekly_prompt_commented(user_id: int, week_start: date) -> None:
    async with AsyncSessionFactory() as session:
        prompt = await session.scalar(
            select(WeeklyPrompt).where(
                WeeklyPrompt.user_id == user_id,
                WeeklyPrompt.week_start == week_start,
            )
        )
        if prompt is not None:
            prompt.comment_saved = True
            await session.commit()


@router.callback_query(F.data.startswith("weekly:comment:"))
async def weekly_comment_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    week_start = _decode_day(callback.data.split(":")[-1])
    await state.update_data(weekly_comment_week_start=week_start.isoformat())
    await state.set_state(WeeklyStates.waiting_weekly_comment)
    await callback.message.answer(
        f"Отправьте текст или голосовой комментарий по неделе, начиная с {week_start.strftime('%d.%m.%Y')}."
    )


@router.message(WeeklyStates.waiting_weekly_comment, F.text)
async def weekly_comment_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer("Комментарий пустой. Отправьте текст или голосовое сообщение.")
        return

    data = await state.get_data()
    week_start = date.fromisoformat(data["weekly_comment_week_start"])
    week_end = week_start + timedelta(days=6)
    user_id = await _resolve_user_id(message.from_user.id)

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        await services.diary_service.create_text_entry(
            user_id=user_id,
            entry_date=date.today(),
            text=(
                f"Итоги недели {week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}\n"
                f"{text}"
            ),
            tags="weekly_review",
        )

    await _mark_weekly_prompt_commented(user_id=user_id, week_start=week_start)
    await state.clear()
    await message.answer("Комментарий к неделе сохранен в дневник ✅")


@router.message(WeeklyStates.waiting_weekly_comment, F.voice)
async def weekly_comment_voice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    week_start = date.fromisoformat(data["weekly_comment_week_start"])
    user_id = await _resolve_user_id(message.from_user.id)
    voice = message.voice

    settings = get_settings()
    transcription_service = create_transcription_service(settings)

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

        attempts = 0
        last_error = None
        transcript_text = None
        language = None
        confidence = None
        status = "pending"

        for attempt in range(1, 4):
            attempts = attempt
            try:
                result = await transcription_service.transcribe_telegram_voice(
                    bot=message.bot,
                    telegram_file_id=voice.file_id,
                )
                transcript_text = result.text
                language = result.language
                confidence = result.confidence
                status = "done"
                last_error = None
                break
            except Exception as exc:  # pragma: no cover - external branch
                last_error = str(exc)

        if status != "done":
            status = "failed"

        await services.diary_service.save_transcript(
            entry_id=entry.id,
            transcript_text=transcript_text,
            status=status,
            attempts=attempts,
            language=language,
            confidence=confidence,
            last_error=last_error,
        )

    await _mark_weekly_prompt_commented(user_id=user_id, week_start=week_start)
    await state.clear()
    await message.answer("Голосовой комментарий недели сохранен ✅")


@router.message(WeeklyStates.waiting_weekly_comment)
async def weekly_comment_invalid(message: Message) -> None:
    await message.answer("Пришлите текст или голосовой комментарий.")
