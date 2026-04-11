from datetime import datetime

from develop_a_habit.db.models import TimeSlot
from develop_a_habit.domain.time_slots import next_slot, resolve_slot_by_hour


def test_resolve_slot_by_hour():
    assert resolve_slot_by_hour(datetime(2026, 4, 11, 8, 0, 0)) == TimeSlot.MORNING
    assert resolve_slot_by_hour(datetime(2026, 4, 11, 14, 0, 0)) == TimeSlot.DAY
    assert resolve_slot_by_hour(datetime(2026, 4, 11, 20, 0, 0)) == TimeSlot.EVENING


def test_next_slot_cycle():
    assert next_slot(TimeSlot.MORNING) == TimeSlot.DAY
    assert next_slot(TimeSlot.DAY) == TimeSlot.EVENING
    assert next_slot(TimeSlot.EVENING) == TimeSlot.MORNING
