from datetime import datetime

from develop_a_habit.db.models import TimeSlot


def resolve_slot_by_hour(dt: datetime) -> TimeSlot:
    hour = dt.hour
    if hour < 12:
        return TimeSlot.MORNING
    if hour < 18:
        return TimeSlot.DAY
    return TimeSlot.EVENING


def ordered_slots() -> list[TimeSlot]:
    return [TimeSlot.MORNING, TimeSlot.DAY, TimeSlot.EVENING]


def next_slot(slot: TimeSlot) -> TimeSlot:
    slots = ordered_slots()
    index = slots.index(slot)
    return slots[(index + 1) % len(slots)]
