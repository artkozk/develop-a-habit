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
    icon_emoji: str | None = None
    is_sport: bool = False
    sport_base_sets: int | None = None
    sport_base_reps: int | None = None
    sport_linear_step_reps: int | None = None
    sport_progression_enabled: bool = True
    sport_start_date: date | None = None
    schedule_rules: list[ScheduleRuleInput] = field(default_factory=list)


@dataclass(slots=True)
class CheckinInput:
    habit_id: int
    check_date: date
    time_slot: TimeSlot
    status: str
    actual_sets: int | None = None
    actual_reps_csv: str | None = None
    target_sets: int | None = None
    target_reps: int | None = None
    sport_plan_adhered: bool | None = None
    note: str | None = None
