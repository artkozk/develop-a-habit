from datetime import date

from develop_a_habit.db.models import HabitScheduleRule, ScheduleType, TimeSlot


def is_rule_due(rule: HabitScheduleRule, target_date: date, slot: TimeSlot | None = None) -> bool:
    if slot is not None and rule.time_slot != slot:
        return False

    if rule.schedule_type == ScheduleType.DAILY:
        return True

    if rule.schedule_type == ScheduleType.EVERY_OTHER_DAY:
        anchor = rule.start_from or target_date
        days = (target_date - anchor).days
        if days < 0:
            return False
        interval = max(rule.interval_days, 1)
        return days % interval == 0

    if rule.schedule_type == ScheduleType.SPECIFIC_WEEKDAYS:
        if rule.weekday is None:
            return False
        return target_date.weekday() == rule.weekday

    return False
