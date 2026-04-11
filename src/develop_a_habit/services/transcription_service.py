from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import Bot

from develop_a_habit.config import Settings


@dataclass(slots=True)
class TranscriptResult:
    text: str
    language: str | None = None
    confidence: int | None = None


class SpeechToTextProvider:
    async def transcribe(self, file_path: Path) -> TranscriptResult:
        raise NotImplementedError


class MockSpeechToTextProvider(SpeechToTextProvider):
    async def transcribe(self, file_path: Path) -> TranscriptResult:
        name = file_path.name
        return TranscriptResult(text=f"[mock transcription for {name}]", language="ru")


class TranscriptionService:
    def __init__(self, provider: SpeechToTextProvider, retries: int = 3) -> None:
        self.provider = provider
        self.retries = retries

    async def transcribe_telegram_voice(self, bot: Bot, telegram_file_id: str) -> TranscriptResult:
        file = await bot.get_file(telegram_file_id)
        with NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            await bot.download_file(file.file_path, destination=temp_path)
            last_error: Exception | None = None
            for attempt in range(1, self.retries + 1):
                try:
                    return await self.provider.transcribe(temp_path)
                except Exception as exc:  # pragma: no cover - fallback branch
                    last_error = exc
                    if attempt == self.retries:
                        raise
                    await asyncio.sleep(0.5 * attempt)

            assert last_error is not None  # pragma: no cover
            raise last_error
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


def create_transcription_service(settings: Settings) -> TranscriptionService:
    provider_name = settings.stt_provider.lower().strip()
    if provider_name == "mock":
        provider = MockSpeechToTextProvider()
    else:
        provider = MockSpeechToTextProvider()
    return TranscriptionService(provider=provider)
