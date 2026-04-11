from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.db.models import DiaryEntry, DiaryEntryType


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
