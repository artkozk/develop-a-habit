from datetime import date

from develop_a_habit.db.models import HabitScheduleRule, ScheduleType, TimeSlot
from develop_a_habit.domain.schedule_engine import is_rule_due


def test_daily_rule_due():
    rule = HabitScheduleRule(
        habit_id=1,
        schedule_type=ScheduleType.DAILY,
        time_slot=TimeSlot.MORNING,
    )
    assert is_rule_due(rule, date(2026, 4, 11), slot=TimeSlot.MORNING)
    assert not is_rule_due(rule, date(2026, 4, 11), slot=TimeSlot.EVENING)


def test_every_other_day_rule_due():
    rule = HabitScheduleRule(
        habit_id=1,
        schedule_type=ScheduleType.EVERY_OTHER_DAY,
        time_slot=TimeSlot.DAY,
        interval_days=2,
        start_from=date(2026, 4, 10),
    )
    assert is_rule_due(rule, date(2026, 4, 10), slot=TimeSlot.DAY)
    assert not is_rule_due(rule, date(2026, 4, 11), slot=TimeSlot.DAY)
    assert is_rule_due(rule, date(2026, 4, 12), slot=TimeSlot.DAY)


def test_specific_weekday_rule_due():
    # 2026-04-13 is Monday -> weekday=0
    rule = HabitScheduleRule(
        habit_id=1,
        schedule_type=ScheduleType.SPECIFIC_WEEKDAYS,
        time_slot=TimeSlot.EVENING,
        weekday=0,
    )
    assert is_rule_due(rule, date(2026, 4, 13), slot=TimeSlot.EVENING)
    assert not is_rule_due(rule, date(2026, 4, 14), slot=TimeSlot.EVENING)


def test_all_day_rule_matches_all_day_parts():
    rule = HabitScheduleRule(
        habit_id=3,
        schedule_type=ScheduleType.DAILY,
        time_slot=TimeSlot.ALL_DAY,
    )
    target = date(2026, 4, 13)

    assert is_rule_due(rule, target, slot=TimeSlot.MORNING)
    assert is_rule_due(rule, target, slot=TimeSlot.DAY)
    assert is_rule_due(rule, target, slot=TimeSlot.EVENING)
    assert is_rule_due(rule, target, slot=TimeSlot.ALL_DAY)
