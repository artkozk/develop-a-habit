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
    assert result.pullups_reps == 0
    assert result.pushups_reps == 0


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


def test_period_metrics_ignores_future_days():
    monday = date(2026, 4, 13)
    tuesday = date(2026, 4, 14)
    sunday = date(2026, 4, 19)

    habit = _habit(5, HabitType.POSITIVE, TimeSlot.MORNING)
    due_map = {day: [habit] for day in [monday, tuesday, date(2026, 4, 15), date(2026, 4, 16), date(2026, 4, 17), date(2026, 4, 18), sunday]}
    checkin_map = {
        monday: [
            HabitCheckin(
                habit_id=5,
                check_date=monday,
                time_slot=TimeSlot.MORNING,
                status=CheckinStatus.DONE,
            )
        ]
    }

    service = MetricsService(FakeHabitService(due_map=due_map, day_off_dates=set(), checkin_map=checkin_map))
    result = asyncio.run(service.compute_period_metrics(1, monday, sunday, today=tuesday))

    # Only Monday+Tuesday are counted; Wed-Sun are future and ignored.
    assert result.plan_slots == 2
    assert result.completed_slots == 1


def test_stats_include_pullups_and_pushups_reps():
    target = date(2026, 4, 10)
    pullups = _habit(3, HabitType.POSITIVE, TimeSlot.DAY)
    pullups.name = "Подтягивания"
    pullups.is_sport = True
    pullups.sport_base_sets = 2
    pullups.sport_base_reps = 12
    pullups.sport_linear_step_reps = 0
    pullups.sport_progression_enabled = False

    pushups = _habit(4, HabitType.POSITIVE, TimeSlot.DAY)
    pushups.name = "Отжимания"
    pushups.is_sport = True
    pushups.sport_base_sets = 2
    pushups.sport_base_reps = 15
    pushups.sport_linear_step_reps = 0
    pushups.sport_progression_enabled = False

    service = MetricsService(
        FakeHabitService(
            due_map={target: [pullups, pushups]},
            day_off_dates=set(),
            checkin_map={
                target: [
                    HabitCheckin(
                        habit_id=3,
                        check_date=target,
                        time_slot=TimeSlot.DAY,
                        status=CheckinStatus.DONE,
                        target_sets=2,
                        target_reps=12,
                        sport_plan_adhered=True,
                    ),
                    HabitCheckin(
                        habit_id=4,
                        check_date=target,
                        time_slot=TimeSlot.DAY,
                        status=CheckinStatus.DONE,
                        target_sets=2,
                        target_reps=15,
                        sport_plan_adhered=True,
                    ),
                ]
            },
        )
    )
    result = asyncio.run(service.compute_period_metrics(1, target, target, today=target))

    assert result.pullups_reps == 24
    assert result.pushups_reps == 30


def test_combined_exercise_name_counts_for_both_metrics():
    target = date(2026, 4, 10)
    combined = _habit(6, HabitType.POSITIVE, TimeSlot.DAY)
    combined.name = "Отжимания\\подтягивания"
    combined.is_sport = True
    combined.sport_base_sets = 2
    combined.sport_base_reps = 12
    combined.sport_linear_step_reps = 0
    combined.sport_progression_enabled = False

    service = MetricsService(
        FakeHabitService(
            due_map={target: [combined]},
            day_off_dates=set(),
            checkin_map={
                target: [
                    HabitCheckin(
                        habit_id=6,
                        check_date=target,
                        time_slot=TimeSlot.DAY,
                        status=CheckinStatus.DONE,
                        target_sets=2,
                        target_reps=12,
                        sport_plan_adhered=True,
                    ),
                ]
            },
        )
    )
    result = asyncio.run(service.compute_period_metrics(1, target, target, today=target))

    assert result.pullups_reps == 24
    assert result.pushups_reps == 24
