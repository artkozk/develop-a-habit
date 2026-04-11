from datetime import date

from develop_a_habit.db.models import Habit


def compute_linear_target(habit: Habit, target_date: date) -> tuple[int, int] | None:
    if not habit.is_sport:
        return None
    if habit.sport_base_sets is None or habit.sport_base_reps is None:
        return None
    if not habit.sport_progression_enabled:
        return habit.sport_base_sets, habit.sport_base_reps

    start = habit.sport_start_date or target_date
    step = max(habit.sport_linear_step_reps or 0, 0)
    days = (target_date - start).days
    weeks = max(days // 7, 0)
    current_reps = habit.sport_base_reps + weeks * step
    return habit.sport_base_sets, current_reps
