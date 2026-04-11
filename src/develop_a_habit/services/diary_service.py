from datetime import date, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.db.models import DiaryEntry, DiaryEntryType, DiaryTranscript, DiaryVoice


class DiaryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_text_entry(
        self,
        user_id: int,
        entry_date: date,
        text: str,
        tags: str | None = None,
    ) -> DiaryEntry:
        entry = DiaryEntry(
            user_id=user_id,
            entry_date=entry_date,
            entry_type=DiaryEntryType.TEXT,
            text_body=text,
            tags=tags,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def create_voice_entry(
        self,
        user_id: int,
        entry_date: date,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        duration_sec: int | None,
        mime: str | None,
        message_id: int | None,
    ) -> DiaryEntry:
        entry = DiaryEntry(
            user_id=user_id,
            entry_date=entry_date,
            entry_type=DiaryEntryType.VOICE,
            text_body=None,
        )
        self.session.add(entry)
        await self.session.flush()

        voice = DiaryVoice(
            entry_id=entry.id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            duration_sec=duration_sec,
            mime=mime,
            message_id=message_id,
        )
        transcript = DiaryTranscript(
            entry_id=entry.id,
            transcript_text=None,
            stt_status="pending",
            attempts=0,
        )
        self.session.add(voice)
        self.session.add(transcript)

        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def save_transcript(
        self,
        entry_id: int,
        transcript_text: str | None,
        status: str,
        attempts: int,
        language: str | None = None,
        confidence: int | None = None,
        last_error: str | None = None,
    ) -> None:
        transcript = await self.session.scalar(
            select(DiaryTranscript).where(DiaryTranscript.entry_id == entry_id)
        )
        if transcript is None:
            transcript = DiaryTranscript(entry_id=entry_id)
            self.session.add(transcript)

        transcript.transcript_text = transcript_text
        transcript.stt_status = status
        transcript.attempts = attempts
        transcript.language = language
        transcript.confidence = confidence
        transcript.last_error = last_error
        transcript.updated_at = datetime.utcnow()
        await self.session.commit()

    async def list_entries_for_date(self, user_id: int, entry_date: date) -> list[DiaryEntry]:
        query = (
            select(DiaryEntry)
            .where(and_(DiaryEntry.user_id == user_id, DiaryEntry.entry_date == entry_date))
            .order_by(DiaryEntry.created_at.asc())
        )
        result = await self.session.scalars(query)
        return list(result)

    async def has_entries_for_date(self, user_id: int, entry_date: date) -> bool:
        query = (
            select(DiaryEntry.id)
            .where(and_(DiaryEntry.user_id == user_id, DiaryEntry.entry_date == entry_date))
            .limit(1)
        )
        return (await self.session.scalar(query)) is not None

    async def list_entries_range(self, user_id: int, start_date: date, end_date: date) -> list[DiaryEntry]:
        query = (
            select(DiaryEntry)
            .where(
                DiaryEntry.user_id == user_id,
                DiaryEntry.entry_date >= start_date,
                DiaryEntry.entry_date <= end_date,
            )
            .order_by(DiaryEntry.entry_date.asc(), DiaryEntry.created_at.asc())
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_voice_by_entry_id(self, entry_id: int) -> DiaryVoice | None:
        return await self.session.scalar(select(DiaryVoice).where(DiaryVoice.entry_id == entry_id))

    async def get_transcript_by_entry_id(self, entry_id: int) -> DiaryTranscript | None:
        return await self.session.scalar(select(DiaryTranscript).where(DiaryTranscript.entry_id == entry_id))

    async def search_entries(
        self,
        user_id: int,
        query_text: str,
        voice_only: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 20,
    ) -> list[DiaryEntry]:
        query = (
            select(DiaryEntry)
            .outerjoin(DiaryTranscript, DiaryTranscript.entry_id == DiaryEntry.id)
            .outerjoin(DiaryVoice, DiaryVoice.entry_id == DiaryEntry.id)
            .where(DiaryEntry.user_id == user_id)
        )

        if start_date is not None:
            query = query.where(DiaryEntry.entry_date >= start_date)
        if end_date is not None:
            query = query.where(DiaryEntry.entry_date <= end_date)
        if voice_only:
            query = query.where(DiaryVoice.id.is_not(None))

        cleaned = query_text.strip()
        if cleaned:
            ts_query = func.plainto_tsquery("russian", cleaned)
            diary_text_match = func.to_tsvector(
                "russian", func.coalesce(DiaryEntry.text_body, "")
            ).op("@@")(ts_query)
            transcript_match = func.to_tsvector(
                "russian", func.coalesce(DiaryTranscript.transcript_text, "")
            ).op("@@")(ts_query)
            ilike_pattern = f"%{cleaned}%"
            query = query.where(
                or_(
                    diary_text_match,
                    transcript_match,
                    DiaryEntry.text_body.ilike(ilike_pattern),
                    DiaryTranscript.transcript_text.ilike(ilike_pattern),
                )
            )

        query = query.order_by(DiaryEntry.entry_date.desc(), DiaryEntry.created_at.desc()).limit(limit)
        result = await self.session.scalars(query)
        return list(result)
