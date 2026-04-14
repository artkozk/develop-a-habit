from dataclasses import dataclass
from datetime import date, timedelta

from develop_a_habit.db.models import CheckinStatus, Habit, HabitCheckin, HabitType, TimeSlot
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


@dataclass(slots=True)
class HabitProgressResult:
    habit_id: int
    name: str
    icon_emoji: str | None
    weekly_success_days: int
    weekly_due_days: int
    adherence_days_total: int
    current_streak_days: int
    goal_days: int | None
    goal_progress_days: int
    goal_completed_cycles: int
    goal_reached: bool


def _date_range(start_date: date, end_date: date):
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


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
        effective_end = min(end_date, today)
        if effective_end < start_date:
            return MetricsResult(plan_slots=0, completed_slots=0, extra_slots=0)
        plan_slots = 0
        completed_slots = 0
        extra_slots = 0
        pushups_reps = 0
        pullups_reps = 0

        cursor = start_date
        while cursor <= effective_end:
            day_off = await self.habit_service.is_day_off(user_id=user_id, target_date=cursor)
            due_habits = await self.habit_service.list_due_habits(user_id=user_id, target_date=cursor)
            checkins = await self.habit_service.get_checkins_for_date(user_id=user_id, target_date=cursor)
            checkin_map = self._build_checkin_map(checkins)
            habit_map = {habit.id: habit for habit in due_habits}

            for habit in due_habits:
                slots = self._due_slots_for_habit(habit, cursor)
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

                kinds = self._classify_exercise_kinds(habit.name)
                if "pushups" in kinds:
                    pushups_reps += total_reps
                if "pullups" in kinds:
                    pullups_reps += total_reps

            cursor += timedelta(days=1)

        return MetricsResult(
            plan_slots=plan_slots,
            completed_slots=completed_slots,
            extra_slots=extra_slots,
            pushups_reps=pushups_reps,
            pullups_reps=pullups_reps,
        )

    async def compute_habit_progress(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        today: date | None = None,
    ) -> list[HabitProgressResult]:
        today = today or date.today()
        period_start = start_date
        period_end = min(end_date, today)
        habits = await self.habit_service.list_habits(user_id=user_id, active_only=True)
        if not habits:
            return []
        user_created_date = await self.habit_service.get_user_created_date(user_id=user_id)

        history_start = min(
            self._habit_active_from(
                habit=habit,
                target_date=period_start,
                user_created_date=user_created_date,
            )
            for habit in habits
        )
        history_start = min(history_start, period_start)
        if history_start > today:
            history_start = today

        checkins = await self.habit_service.get_checkins_for_range(
            user_id=user_id,
            start_date=history_start,
            end_date=today,
        )
        checkin_map = self._build_day_slot_checkin_map(checkins)
        day_off_exact, day_off_weekdays = await self.habit_service.get_day_off_snapshot(
            user_id=user_id,
            start_date=history_start,
            end_date=today,
        )

        results: list[HabitProgressResult] = []
        for habit in habits:
            adherence_days_total = 0
            weekly_due_days = 0
            weekly_success_days = 0

            for day in _date_range(history_start, today):
                if self._is_day_off(day, day_off_exact, day_off_weekdays):
                    continue
                due_slots = self._due_slots_for_habit(
                    habit,
                    day,
                    user_created_date=user_created_date,
                )
                if not due_slots:
                    continue

                success, _failure = self._day_success(
                    habit=habit,
                    day=day,
                    today=today,
                    due_slots=due_slots,
                    checkin_map=checkin_map,
                )
                if success:
                    adherence_days_total += 1

                if period_start <= day <= period_end:
                    weekly_due_days += 1
                    if success:
                        weekly_success_days += 1

            current_streak_days = self._current_streak(
                habit=habit,
                history_start=history_start,
                today=today,
                day_off_exact=day_off_exact,
                day_off_weekdays=day_off_weekdays,
                checkin_map=checkin_map,
                user_created_date=user_created_date,
            )

            goal_progress_days = 0
            goal_reached = False
            if habit.goal_days is not None and habit.goal_days > 0 and habit.goal_start_date is not None:
                goal_from = max(habit.goal_start_date, history_start)
                for day in _date_range(goal_from, today):
                    if self._is_day_off(day, day_off_exact, day_off_weekdays):
                        continue
                    due_slots = self._due_slots_for_habit(
                        habit,
                        day,
                        user_created_date=user_created_date,
                    )
                    if not due_slots:
                        continue
                    success, _failure = self._day_success(
                        habit=habit,
                        day=day,
                        today=today,
                        due_slots=due_slots,
                        checkin_map=checkin_map,
                    )
                    if success:
                        goal_progress_days += 1
                goal_reached = goal_progress_days >= habit.goal_days

            results.append(
                HabitProgressResult(
                    habit_id=habit.id,
                    name=habit.name,
                    icon_emoji=habit.icon_emoji,
                    weekly_success_days=weekly_success_days,
                    weekly_due_days=weekly_due_days,
                    adherence_days_total=adherence_days_total,
                    current_streak_days=current_streak_days,
                    goal_days=habit.goal_days,
                    goal_progress_days=goal_progress_days,
                    goal_completed_cycles=habit.goal_completed_cycles or 0,
                    goal_reached=goal_reached,
                )
            )

        return results

    def _current_streak(
        self,
        habit: Habit,
        history_start: date,
        today: date,
        day_off_exact: set[date],
        day_off_weekdays: set[int],
        checkin_map: dict[tuple[int, date, str], HabitCheckin],
        user_created_date: date | None = None,
    ) -> int:
        streak = 0
        cursor = today
        while cursor >= history_start:
            if self._is_day_off(cursor, day_off_exact, day_off_weekdays):
                cursor -= timedelta(days=1)
                continue
            due_slots = self._due_slots_for_habit(
                habit,
                cursor,
                user_created_date=user_created_date,
            )
            if not due_slots:
                cursor -= timedelta(days=1)
                continue

            success, explicit_failure = self._day_success(
                habit=habit,
                day=cursor,
                today=today,
                due_slots=due_slots,
                checkin_map=checkin_map,
            )
            if success:
                streak += 1
                cursor -= timedelta(days=1)
                continue

            if cursor == today and not explicit_failure:
                cursor -= timedelta(days=1)
                continue
            break

        return streak

    @staticmethod
    def _habit_active_from(
        habit: Habit,
        target_date: date,
        user_created_date: date | None = None,
    ) -> date:
        active_from = habit.created_at.date() if habit.created_at is not None else target_date
        if user_created_date is not None and active_from == user_created_date:
            return user_created_date + timedelta(days=1)
        return active_from

    @classmethod
    def _due_slots_for_habit(
        cls,
        habit: Habit,
        target_date: date,
        user_created_date: date | None = None,
    ) -> set[TimeSlot]:
        active_from = cls._habit_active_from(
            habit=habit,
            target_date=target_date,
            user_created_date=user_created_date,
        )
        if target_date < active_from:
            return set()
        return {
            rule.time_slot
            for rule in habit.schedule_rules
            if is_rule_due(rule, target_date=target_date, slot=None)
        }

    @classmethod
    def _day_success(
        cls,
        habit: Habit,
        day: date,
        today: date,
        due_slots: set[TimeSlot],
        checkin_map: dict[tuple[int, date, str], HabitCheckin],
    ) -> tuple[bool, bool]:
        all_success = True
        explicit_failure = False
        for slot in due_slots:
            checkin = checkin_map.get((habit.id, day, slot.value))
            if checkin is not None and checkin.status in {CheckinStatus.MISSED, CheckinStatus.VIOLATED}:
                explicit_failure = True
            if not cls._is_mandatory_success(habit, checkin, target_date=day, today=today):
                all_success = False
        return all_success, explicit_failure

    @staticmethod
    def _is_day_off(target_date: date, exact_days: set[date], weekdays: set[int]) -> bool:
        if target_date in exact_days:
            return True
        return target_date.weekday() in weekdays

    @staticmethod
    def _build_checkin_map(checkins: list[HabitCheckin]) -> dict[tuple[int, str], HabitCheckin]:
        return {(checkin.habit_id, checkin.time_slot.value): checkin for checkin in checkins}

    @staticmethod
    def _build_day_slot_checkin_map(
        checkins: list[HabitCheckin],
    ) -> dict[tuple[int, date, str], HabitCheckin]:
        return {(checkin.habit_id, checkin.check_date, checkin.time_slot.value): checkin for checkin in checkins}

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

        if habit.habit_type == HabitType.NEGATIVE:
            return True

        return False

    @staticmethod
    def _classify_exercise_kinds(name: str) -> set[str]:
        value = name.lower()
        result: set[str] = set()
        if "отжим" in value or "push" in value:
            result.add("pushups")
        if "подтяг" in value or "pull" in value:
            result.add("pullups")
        return result

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
