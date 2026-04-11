import asyncio
from datetime import date

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


class FakeHabitService:
    def __init__(self, due_map, day_off_dates, checkin_map):
        self.due_map = due_map
        self.day_off_dates = day_off_dates
        self.checkin_map = checkin_map

    async def is_day_off(self, user_id: int, target_date: date) -> bool:
        return target_date in self.day_off_dates

    async def list_due_habits(self, user_id: int, target_date: date, slot=None):
        return self.due_map.get(target_date, [])

    async def get_checkins_for_date(self, user_id: int, target_date: date):
        return self.checkin_map.get(target_date, [])


def _habit(habit_id: int, habit_type: HabitType, slot: TimeSlot) -> Habit:
    habit = Habit(id=habit_id, user_id=1, name=f"H{habit_id}", habit_type=habit_type)
    habit.schedule_rules = [
        HabitScheduleRule(
            habit_id=habit_id,
            schedule_type=ScheduleType.DAILY,
            time_slot=slot,
        )
    ]
    return habit


def test_metrics_plan_and_over_plan():
    first = date(2026, 4, 10)
    second = date(2026, 4, 11)

    habit = _habit(1, HabitType.POSITIVE, TimeSlot.MORNING)
    due_map = {first: [habit], second: [habit]}
    day_off = {second}
    checkin_map = {
        first: [
            HabitCheckin(
                habit_id=1,
                check_date=first,
                time_slot=TimeSlot.MORNING,
                status=CheckinStatus.DONE,
            )
        ],
        second: [
            HabitCheckin(
                habit_id=1,
                check_date=second,
                time_slot=TimeSlot.MORNING,
                status=CheckinStatus.OPTIONAL_DONE,
            )
        ],
    }

    service = MetricsService(FakeHabitService(due_map, day_off, checkin_map))
    result = asyncio.run(service.compute_period_metrics(1, first, second, today=second))

    assert result.plan_slots == 1
    assert result.completed_slots == 1
    assert result.extra_slots == 1
    assert result.plan_completion == 100.0
    assert result.over_completion == 200.0


def test_negative_past_without_violation_counts_success():
    target = date(2026, 4, 9)
    negative_habit = _habit(2, HabitType.NEGATIVE, TimeSlot.DAY)

    service = MetricsService(
        FakeHabitService(
            due_map={target: [negative_habit]},
            day_off_dates=set(),
            checkin_map={target: []},
        )
    )
    result = asyncio.run(service.compute_period_metrics(1, target, target, today=date(2026, 4, 11)))

    assert result.plan_slots == 1
    assert result.completed_slots == 1
    assert result.plan_completion == 100.0
