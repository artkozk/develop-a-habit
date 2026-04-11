from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.db.models import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_by_telegram_id(self, telegram_user_id: int, timezone: str) -> User:
        query = select(User).where(User.telegram_user_id == telegram_user_id)
        user = await self.session.scalar(query)
        if user is not None:
            return user

        user = User(telegram_user_id=telegram_user_id, timezone=timezone)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = select(User).where(User.telegram_user_id == telegram_user_id)
        return await self.session.scalar(query)
