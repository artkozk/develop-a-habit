from dataclasses import dataclass, field
from datetime import date

from develop_a_habit.db.models import HabitType, ScheduleType, TimeSlot


@dataclass(slots=True)
class ScheduleRuleInput:
    schedule_type: ScheduleType
    time_slot: TimeSlot
    weekday: int | None = None
    interval_days: int = 1
    start_from: date | None = None


@dataclass(slots=True)
class HabitCreateInput:
    name: str
    habit_type: HabitType
    schedule_rules: list[ScheduleRuleInput] = field(default_factory=list)


@dataclass(slots=True)
class CheckinInput:
    habit_id: int
    check_date: date
    time_slot: TimeSlot
    status: str
    note: str | None = None
