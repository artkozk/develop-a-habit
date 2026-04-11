from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from develop_a_habit.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session
