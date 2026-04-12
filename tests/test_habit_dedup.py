from datetime import date

from develop_a_habit.db.models import CheckinStatus, HabitCheckin, HabitType, TimeSlot
from develop_a_habit.services.habit_service import HabitService


def test_prefer_checkin_positive_prefers_done_over_missed():
    done = HabitCheckin(
        habit_id=1,
        check_date=date(2026, 4, 12),
        time_slot=TimeSlot.MORNING,
        status=CheckinStatus.DONE,
    )
    missed = HabitCheckin(
        habit_id=2,
        check_date=date(2026, 4, 12),
        time_slot=TimeSlot.MORNING,
        status=CheckinStatus.MISSED,
    )

    winner = HabitService._prefer_checkin(HabitType.POSITIVE, missed, done)
    assert winner.status == CheckinStatus.DONE


def test_prefer_checkin_negative_prefers_violated():
    ok_status = HabitCheckin(
        habit_id=1,
        check_date=date(2026, 4, 12),
        time_slot=TimeSlot.EVENING,
        status=CheckinStatus.DONE,
    )
    violated = HabitCheckin(
        habit_id=2,
        check_date=date(2026, 4, 12),
        time_slot=TimeSlot.EVENING,
        status=CheckinStatus.VIOLATED,
    )

    winner = HabitService._prefer_checkin(HabitType.NEGATIVE, ok_status, violated)
    assert winner.status == CheckinStatus.VIOLATED
