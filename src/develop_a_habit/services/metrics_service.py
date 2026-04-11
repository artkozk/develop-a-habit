from dataclasses import dataclass
from datetime import date, timedelta

from develop_a_habit.db.models import CheckinStatus, Habit, HabitCheckin, HabitType
from develop_a_habit.domain.schedule_engine import is_rule_due
from develop_a_habit.services.habit_service import HabitService


@dataclass(slots=True)
class MetricsResult:
    plan_slots: int
    completed_slots: int
    extra_slots: int

    @property
    def plan_completion(self) -> float:
        if self.plan_slots == 0:
            return 0.0
        return round(self.completed_slots / self.plan_slots * 100.0, 2)

    @property
    def over_completion(self) -> float:
        if self.plan_slots == 0:
            return 0.0
        return round((self.completed_slots + self.extra_slots) / self.plan_slots * 100.0, 2)


class MetricsService:
    def __init__(self, habit_service: HabitService):
        self.habit_service = habit_service

    async def compute_period_metrics(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        today: date | None = None,
    ) -> MetricsResult:
        today = today or date.today()
        plan_slots = 0
        completed_slots = 0
        extra_slots = 0

        cursor = start_date
        while cursor <= end_date:
            day_off = await self.habit_service.is_day_off(user_id=user_id, target_date=cursor)
            due_habits = await self.habit_service.list_due_habits(user_id=user_id, target_date=cursor)
            checkins = await self.habit_service.get_checkins_for_date(user_id=user_id, target_date=cursor)
            checkin_map = self._build_checkin_map(checkins)

            for habit in due_habits:
                slots = {
                    rule.time_slot
                    for rule in habit.schedule_rules
                    if is_rule_due(rule, target_date=cursor, slot=None)
                }
                for slot in slots:
                    key = (habit.id, slot.value)
                    checkin = checkin_map.get(key)
                    if day_off:
                        if self._is_extra_success(habit, checkin):
                            extra_slots += 1
                        continue

                    plan_slots += 1
                    if self._is_mandatory_success(habit, checkin, target_date=cursor, today=today):
                        completed_slots += 1

            cursor += timedelta(days=1)

        return MetricsResult(
            plan_slots=plan_slots,
            completed_slots=completed_slots,
            extra_slots=extra_slots,
        )

    @staticmethod
    def _build_checkin_map(checkins: list[HabitCheckin]) -> dict[tuple[int, str], HabitCheckin]:
        return {(checkin.habit_id, checkin.time_slot.value): checkin for checkin in checkins}

    @staticmethod
    def _is_extra_success(habit: Habit, checkin: HabitCheckin | None) -> bool:
        if checkin is None:
            return False

        if habit.habit_type == HabitType.POSITIVE:
            return checkin.status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}

        return checkin.status != CheckinStatus.VIOLATED

    @staticmethod
    def _is_mandatory_success(
        habit: Habit,
        checkin: HabitCheckin | None,
        target_date: date,
        today: date,
    ) -> bool:
        if checkin is not None:
            if habit.habit_type == HabitType.POSITIVE:
                return checkin.status in {CheckinStatus.DONE, CheckinStatus.OPTIONAL_DONE}
            return checkin.status != CheckinStatus.VIOLATED

        if habit.habit_type == HabitType.NEGATIVE and target_date < today:
            return True

        return False
