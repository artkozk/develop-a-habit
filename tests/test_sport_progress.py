from datetime import date

from develop_a_habit.db.models import Habit, HabitType
from develop_a_habit.domain.sport_progress import compute_linear_target


def test_linear_target_growth_by_weeks():
    habit = Habit(
        id=1,
        user_id=1,
        name="Подтягивания",
        habit_type=HabitType.POSITIVE,
        is_sport=True,
        sport_base_sets=3,
        sport_base_reps=8,
        sport_linear_step_reps=1,
        sport_progression_enabled=True,
        sport_start_date=date(2026, 4, 1),
    )

    assert compute_linear_target(habit, date(2026, 4, 1)) == (3, 8)
    assert compute_linear_target(habit, date(2026, 4, 8)) == (3, 9)
    assert compute_linear_target(habit, date(2026, 4, 15)) == (3, 10)


def test_linear_target_disabled_progression_returns_base():
    habit = Habit(
        id=3,
        user_id=1,
        name="Отжимания",
        habit_type=HabitType.POSITIVE,
        is_sport=True,
        sport_base_sets=2,
        sport_base_reps=15,
        sport_linear_step_reps=2,
        sport_progression_enabled=False,
        sport_start_date=date(2026, 4, 1),
    )

    assert compute_linear_target(habit, date(2026, 5, 1)) == (2, 15)


def test_non_sport_has_no_target():
    habit = Habit(
        id=2,
        user_id=1,
        name="Чтение",
        habit_type=HabitType.POSITIVE,
        is_sport=False,
    )
    assert compute_linear_target(habit, date(2026, 4, 1)) is None
