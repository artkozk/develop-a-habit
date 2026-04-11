from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select

from develop_a_habit.config import Settings
from develop_a_habit.db.models import DiaryTranscript, DiaryVoice
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import build_services, create_transcription_service

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TranscriptionTask:
    entry_id: int
    telegram_file_id: str


_QUEUE: asyncio.Queue[TranscriptionTask] = asyncio.Queue()
_SEEN_ENTRY_IDS: set[int] = set()


async def enqueue_transcription(entry_id: int, telegram_file_id: str) -> None:
    if entry_id in _SEEN_ENTRY_IDS:
        return
    _SEEN_ENTRY_IDS.add(entry_id)
    await _QUEUE.put(TranscriptionTask(entry_id=entry_id, telegram_file_id=telegram_file_id))


async def _restore_pending_transcriptions() -> None:
    async with AsyncSessionFactory() as session:
        rows = await session.execute(
            select(DiaryTranscript.entry_id, DiaryVoice.telegram_file_id)
            .join(DiaryVoice, DiaryVoice.entry_id == DiaryTranscript.entry_id)
            .where(DiaryTranscript.stt_status == "pending")
            .order_by(DiaryTranscript.entry_id.asc())
        )
        for entry_id, telegram_file_id in rows:
            await enqueue_transcription(entry_id=entry_id, telegram_file_id=telegram_file_id)


async def _process_task(bot: Bot, settings: Settings, task: TranscriptionTask) -> None:
    transcription_service = create_transcription_service(settings)
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
                bot=bot,
                telegram_file_id=task.telegram_file_id,
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

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        await services.diary_service.save_transcript(
            entry_id=task.entry_id,
            transcript_text=transcript_text,
            status=status,
            attempts=attempts,
            language=language,
            confidence=confidence,
            last_error=last_error,
        )


async def transcription_worker_loop(bot: Bot, settings: Settings) -> None:
    await _restore_pending_transcriptions()
    while True:
        task = await _QUEUE.get()
        try:
            await _process_task(bot=bot, settings=settings, task=task)
        except Exception:
            logger.exception("Failed to process transcription queue task for entry_id=%s", task.entry_id)
        finally:
            _SEEN_ENTRY_IDS.discard(task.entry_id)
            _QUEUE.task_done()
