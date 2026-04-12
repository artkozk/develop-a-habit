import asyncio
from datetime import date, datetime

from develop_a_habit.db.models import (
    CheckinStatus,
    Habit,
    HabitCheckin,
    HabitScheduleRule,
    HabitType,
    ScheduleType,
    TimeSlot,
)
from develop_a_habit.services.metrics_service import MetricsService


class FakeHabitProgressService:
    def __init__(self, habits, checkins, day_off_exact=None, day_off_weekdays=None):
        self._habits = habits
        self._checkins = checkins
        self._day_off_exact = day_off_exact or set()
        self._day_off_weekdays = day_off_weekdays or set()

    async def list_habits(self, user_id: int, active_only: bool = True):
        return self._habits

    async def get_checkins_for_range(self, user_id: int, start_date: date, end_date: date):
        return [
            checkin
            for checkin in self._checkins
            if start_date <= checkin.check_date <= end_date
        ]

    async def get_day_off_snapshot(self, user_id: int, start_date: date, end_date: date):
        exact = {d for d in self._day_off_exact if start_date <= d <= end_date}
        return exact, set(self._day_off_weekdays)


def test_habit_progress_counts_streak_and_goal():
    habit = Habit(
        id=1,
        user_id=1,
        name="Подтягивания",
        habit_type=HabitType.POSITIVE,
        created_at=datetime(2026, 4, 7),
        goal_days=3,
        goal_start_date=date(2026, 4, 7),
        goal_completed_cycles=1,
    )
    habit.schedule_rules = [
        HabitScheduleRule(
            habit_id=1,
            schedule_type=ScheduleType.DAILY,
            time_slot=TimeSlot.DAY,
        )
    ]

    checkins = [
        HabitCheckin(
            habit_id=1,
            check_date=date(2026, 4, 7),
            time_slot=TimeSlot.DAY,
            status=CheckinStatus.DONE,
        ),
        HabitCheckin(
            habit_id=1,
            check_date=date(2026, 4, 8),
            time_slot=TimeSlot.DAY,
            status=CheckinStatus.DONE,
        ),
        HabitCheckin(
            habit_id=1,
            check_date=date(2026, 4, 10),
            time_slot=TimeSlot.DAY,
            status=CheckinStatus.DONE,
        ),
    ]

    service = MetricsService(FakeHabitProgressService([habit], checkins))
    result = asyncio.run(
        service.compute_habit_progress(
            user_id=1,
            start_date=date(2026, 4, 7),
            end_date=date(2026, 4, 13),
            today=date(2026, 4, 11),
        )
    )

    assert len(result) == 1
    item = result[0]
    assert item.weekly_due_days == 5
    assert item.weekly_success_days == 3
    assert item.adherence_days_total == 3
    assert item.current_streak_days == 1
    assert item.goal_progress_days == 3
    assert item.goal_reached is True
    assert item.goal_completed_cycles == 1


def test_habit_progress_ignores_days_before_habit_creation():
    habit = Habit(
        id=10,
        user_id=1,
        name="Не есть сладкое",
        habit_type=HabitType.NEGATIVE,
        created_at=datetime(2026, 4, 11, 9, 0, 0),
        goal_days=30,
        goal_start_date=date(2026, 4, 11),
        goal_completed_cycles=0,
    )
    habit.schedule_rules = [
        HabitScheduleRule(
            habit_id=10,
            schedule_type=ScheduleType.DAILY,
            time_slot=TimeSlot.ALL_DAY,
        )
    ]

    # No checkins: for negative habits past days are treated as success,
    # but days before creation must not be counted.
    service = MetricsService(FakeHabitProgressService([habit], checkins=[]))
    result = asyncio.run(
        service.compute_habit_progress(
            user_id=1,
            start_date=date(2026, 4, 7),
            end_date=date(2026, 4, 13),
            today=date(2026, 4, 12),
        )
    )

    item = result[0]
    assert item.adherence_days_total == 1
    assert item.weekly_due_days == 2
    assert item.weekly_success_days == 1
    assert item.current_streak_days == 1
