from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.services.diary_service import DiaryService


@dataclass(slots=True)
class ExportResult:
    archive_path: Path
    entries_count: int


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.diary_service = DiaryService(session)

    async def export_diary_zip(self, bot: Bot, user_id: int) -> ExportResult:
        entries = await self.diary_service.list_entries_range(
            user_id=user_id,
            start_date=date(1970, 1, 1),
            end_date=date(2999, 12, 31),
        )

        with TemporaryDirectory(prefix="diary_export_") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            diary_dir = temp_dir / "diary"
            media_dir = temp_dir / "media"
            diary_dir.mkdir(parents=True, exist_ok=True)
            media_dir.mkdir(parents=True, exist_ok=True)

            grouped: dict[date, list] = {}
            for entry in entries:
                grouped.setdefault(entry.entry_date, []).append(entry)

            for day, day_entries in grouped.items():
                md_path = diary_dir / f"{day.isoformat()}.md"
                lines: list[str] = [f"# Дневник за {day.isoformat()}", ""]
                for idx, entry in enumerate(day_entries, start=1):
                    lines.append(f"## Запись {idx} (ID {entry.id})")
                    lines.append(f"- Тип: {entry.entry_type.value}")
                    lines.append(f"- Создано: {entry.created_at.isoformat()}")
                    if entry.tags:
                        lines.append(f"- Теги: {entry.tags}")

                    if entry.text_body:
                        lines.append("")
                        lines.append("### Текст")
                        lines.append(entry.text_body)

                    transcript = await self.diary_service.get_transcript_by_entry_id(entry.id)
                    if transcript and transcript.transcript_text:
                        lines.append("")
                        lines.append("### Транскрипция")
                        lines.append(transcript.transcript_text)
                        lines.append(f"- Статус STT: {transcript.stt_status}")

                    voice = await self.diary_service.get_voice_by_entry_id(entry.id)
                    if voice is not None:
                        ext = ".ogg"
                        media_name = f"entry_{entry.id}{ext}"
                        media_path = media_dir / media_name
                        await self._download_voice(bot=bot, file_id=voice.telegram_file_id, destination=media_path)
                        lines.append("")
                        lines.append("### Голосовое")
                        lines.append(f"- Файл: media/{media_name}")

                    lines.append("")
                    lines.append("---")
                    lines.append("")

                md_path.write_text("\n".join(lines), encoding="utf-8")

            archive_path = temp_dir / f"diary_export_{user_id}_{date.today().isoformat()}.zip"
            with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
                for file_path in temp_dir.rglob("*"):
                    if file_path == archive_path:
                        continue
                    if file_path.is_file():
                        archive.write(file_path, arcname=file_path.relative_to(temp_dir))

            exports_dir = Path("exports")
            exports_dir.mkdir(parents=True, exist_ok=True)
            final_path = exports_dir / archive_path.name
            final_path.write_bytes(archive_path.read_bytes())

        return ExportResult(archive_path=final_path, entries_count=len(entries))

    async def _download_voice(self, bot: Bot, file_id: str, destination: Path) -> None:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=destination)
