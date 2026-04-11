from dataclasses import dataclass
from datetime import date, timedelta

from develop_a_habit.db.models import CheckinStatus, Habit, HabitCheckin, HabitType
from develop_a_habit.domain.schedule_engine import is_rule_due
from develop_a_habit.domain.sport_progress import compute_linear_target
from develop_a_habit.services.habit_service import HabitService


@dataclass(slots=True)
class MetricsResult:
    plan_slots: int
    completed_slots: int
    extra_slots: int
    pushups_reps: int = 0
    pullups_reps: int = 0

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
        pushups_reps = 0
        pullups_reps = 0

        cursor = start_date
        while cursor <= end_date:
            day_off = await self.habit_service.is_day_off(user_id=user_id, target_date=cursor)
            due_habits = await self.habit_service.list_due_habits(user_id=user_id, target_date=cursor)
            checkins = await self.habit_service.get_checkins_for_date(user_id=user_id, target_date=cursor)
            checkin_map = self._build_checkin_map(checkins)
            habit_map = {habit.id: habit for habit in due_habits}

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

            for checkin in checkins:
                habit = habit_map.get(checkin.habit_id)
                if habit is None:
                    continue
                if not self._is_extra_success(habit, checkin):
                    continue

                total_reps = self._resolve_sport_reps(habit, checkin, target_date=cursor)
                if total_reps <= 0:
                    continue

                kind = self._classify_exercise_kind(habit.name)
                if kind == "pushups":
                    pushups_reps += total_reps
                elif kind == "pullups":
                    pullups_reps += total_reps

            cursor += timedelta(days=1)

        return MetricsResult(
            plan_slots=plan_slots,
            completed_slots=completed_slots,
            extra_slots=extra_slots,
            pushups_reps=pushups_reps,
            pullups_reps=pullups_reps,
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

    @staticmethod
    def _classify_exercise_kind(name: str) -> str | None:
        value = name.lower()
        if "отжим" in value or "push" in value:
            return "pushups"
        if "подтяг" in value or "pull" in value:
            return "pullups"
        return None

    @staticmethod
    def _parse_actual_reps_csv(actual_reps_csv: str | None) -> int:
        if not actual_reps_csv:
            return 0
        total = 0
        for piece in actual_reps_csv.split(","):
            piece = piece.strip()
            if piece.isdigit():
                total += int(piece)
        return total

    @classmethod
    def _resolve_sport_reps(cls, habit: Habit, checkin: HabitCheckin, target_date: date) -> int:
        if not habit.is_sport:
            return 0
        if checkin.sport_plan_adhered is False:
            return 0

        actual_total = cls._parse_actual_reps_csv(checkin.actual_reps_csv)
        if actual_total > 0:
            return actual_total

        if checkin.target_sets is not None and checkin.target_reps is not None:
            return checkin.target_sets * checkin.target_reps

        target = compute_linear_target(habit, target_date=target_date)
        if target is None:
            return 0
        sets, reps = target
        return sets * reps
