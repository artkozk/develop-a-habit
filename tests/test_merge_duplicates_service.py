import asyncio
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from develop_a_habit.db.base import Base
from develop_a_habit.db.models import (
    CheckinStatus,
    Habit,
    HabitCheckin,
    HabitScheduleRule,
    HabitType,
    ScheduleType,
    TimeSlot,
    User,
)
from develop_a_habit.services.habit_service import HabitService

pytest.importorskip("aiosqlite")


def test_merge_duplicate_habits_keeps_rules_and_checkins():
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session:
            user = User(telegram_user_id=111, timezone="Europe/Moscow")
            session.add(user)
            await session.flush()

            h1 = Habit(user_id=user.id, name="Зарядка", habit_type=HabitType.POSITIVE)
            h2 = Habit(user_id=user.id, name="Зарядка", habit_type=HabitType.POSITIVE)
            session.add_all([h1, h2])
            await session.flush()

            session.add_all(
                [
                    HabitScheduleRule(
                        habit_id=h1.id,
                        schedule_type=ScheduleType.DAILY,
                        time_slot=TimeSlot.MORNING,
                    ),
                    HabitScheduleRule(
                        habit_id=h2.id,
                        schedule_type=ScheduleType.DAILY,
                        time_slot=TimeSlot.EVENING,
                    ),
                    HabitCheckin(
                        habit_id=h1.id,
                        check_date=date(2026, 4, 11),
                        time_slot=TimeSlot.MORNING,
                        status=CheckinStatus.DONE,
                    ),
                    HabitCheckin(
                        habit_id=h2.id,
                        check_date=date(2026, 4, 11),
                        time_slot=TimeSlot.EVENING,
                        status=CheckinStatus.DONE,
                    ),
                ]
            )
            await session.commit()

            service = HabitService(session)
            merged = await service.merge_duplicate_habits_by_name(user.id)
            assert merged == 1

            habits = list(
                await session.scalars(
                    select(Habit)
                    .where(Habit.user_id == user.id)
                    .options(
                        selectinload(Habit.schedule_rules),
                        selectinload(Habit.checkins),
                    )
                )
            )
            assert len(habits) == 1
            slots = sorted({rule.time_slot.value for rule in habits[0].schedule_rules})
            assert slots == [TimeSlot.EVENING.value, TimeSlot.MORNING.value]
            assert len(habits[0].checkins) == 2

        await engine.dispose()

    asyncio.run(scenario())
