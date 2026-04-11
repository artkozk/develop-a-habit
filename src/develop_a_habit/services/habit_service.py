from datetime import date

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from develop_a_habit.db.models import (
    CheckinStatus,
    DayOffRule,
    Habit,
    HabitCheckin,
    HabitScheduleRule,
    TimeSlot,
)
from develop_a_habit.domain.schedule_engine import is_rule_due
from develop_a_habit.services.dto import CheckinInput, HabitCreateInput


class HabitService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_habit(self, user_id: int, payload: HabitCreateInput) -> Habit:
        habit = Habit(
            user_id=user_id,
            name=payload.name,
            icon_emoji=payload.icon_emoji,
            habit_type=payload.habit_type,
        )
        self.session.add(habit)
        await self.session.flush()

        for rule in payload.schedule_rules:
            self.session.add(
                HabitScheduleRule(
                    habit_id=habit.id,
                    schedule_type=rule.schedule_type,
                    time_slot=rule.time_slot,
                    weekday=rule.weekday,
                    interval_days=max(rule.interval_days, 1),
                    start_from=rule.start_from,
                )
            )

        await self.session.commit()
        await self.session.refresh(habit)
        return habit

    async def list_habits(self, user_id: int, active_only: bool = True) -> list[Habit]:
        query = select(Habit).where(Habit.user_id == user_id).options(selectinload(Habit.schedule_rules))
        if active_only:
            query = query.where(Habit.is_active.is_(True))
        query = query.order_by(Habit.created_at.asc())
        result = await self.session.scalars(query)
        return list(result)

    async def delete_habit(self, user_id: int, habit_id: int) -> bool:
        habit = await self.session.scalar(
            select(Habit).where(and_(Habit.id == habit_id, Habit.user_id == user_id))
        )
        if habit is None:
            return False

        await self.session.delete(habit)
        await self.session.commit()
        return True

    async def list_due_habits(
        self, user_id: int, target_date: date, slot: TimeSlot | None = None
    ) -> list[Habit]:
        habits = await self.list_habits(user_id=user_id, active_only=True)
        due: list[Habit] = []
        for habit in habits:
            if any(is_rule_due(rule, target_date, slot=slot) for rule in habit.schedule_rules):
                due.append(habit)
        return due

    async def is_day_off(self, user_id: int, target_date: date) -> bool:
        query = select(DayOffRule).where(DayOffRule.user_id == user_id)
        rules = list(await self.session.scalars(query))
        weekday = target_date.weekday()
        for rule in rules:
            if rule.exact_date == target_date:
                return True
            if rule.weekday is not None and rule.weekday == weekday:
                return True
        return False

    async def replace_day_off_weekdays(self, user_id: int, weekdays: list[int]) -> None:
        await self.session.execute(
            delete(DayOffRule).where(DayOffRule.user_id == user_id, DayOffRule.weekday.is_not(None))
        )
        for weekday in sorted(set(weekdays)):
            self.session.add(DayOffRule(user_id=user_id, weekday=weekday))
        await self.session.commit()

    async def add_day_off_date(self, user_id: int, exact_date: date) -> None:
        exists = await self.session.scalar(
            select(DayOffRule).where(
                DayOffRule.user_id == user_id,
                DayOffRule.exact_date == exact_date,
            )
        )
        if exists is None:
            self.session.add(DayOffRule(user_id=user_id, exact_date=exact_date))
        await self.session.commit()

    async def remove_day_off_date(self, user_id: int, exact_date: date) -> None:
        rule = await self.session.scalar(
            select(DayOffRule).where(
                DayOffRule.user_id == user_id,
                DayOffRule.exact_date == exact_date,
            )
        )
        if rule is not None:
            await self.session.delete(rule)
            await self.session.commit()

    async def list_day_off_dates(self, user_id: int, start_date: date, end_date: date) -> set[date]:
        query = select(DayOffRule).where(
            DayOffRule.user_id == user_id,
            DayOffRule.exact_date.is_not(None),
            DayOffRule.exact_date >= start_date,
            DayOffRule.exact_date <= end_date,
        )
        rules = list(await self.session.scalars(query))
        return {rule.exact_date for rule in rules if rule.exact_date is not None}

    async def upsert_checkin(self, user_id: int, payload: CheckinInput) -> HabitCheckin:
        habit = await self.session.scalar(
            select(Habit).where(and_(Habit.id == payload.habit_id, Habit.user_id == user_id))
        )
        if habit is None:
            raise ValueError("Habit is not found for current user")

        query = select(HabitCheckin).where(
            and_(
                HabitCheckin.habit_id == payload.habit_id,
                HabitCheckin.check_date == payload.check_date,
                HabitCheckin.time_slot == payload.time_slot,
            )
        )
        checkin = await self.session.scalar(query)
        status = CheckinStatus(payload.status)

        if checkin is None:
            checkin = HabitCheckin(
                habit_id=payload.habit_id,
                check_date=payload.check_date,
                time_slot=payload.time_slot,
                status=status,
                note=payload.note,
            )
            self.session.add(checkin)
        else:
            checkin.status = status
            checkin.note = payload.note

        await self.session.commit()
        await self.session.refresh(checkin)
        return checkin

    async def get_last_checkin(self, user_id: int, habit_id: int) -> HabitCheckin | None:
        habit = await self.session.scalar(
            select(Habit).where(and_(Habit.id == habit_id, Habit.user_id == user_id))
        )
        if habit is None:
            return None

        query = (
            select(HabitCheckin)
            .where(HabitCheckin.habit_id == habit_id)
            .order_by(HabitCheckin.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(query)

    async def get_checkin(
        self, user_id: int, habit_id: int, check_date: date, slot: TimeSlot
    ) -> HabitCheckin | None:
        habit = await self.session.scalar(
            select(Habit).where(and_(Habit.id == habit_id, Habit.user_id == user_id))
        )
        if habit is None:
            return None

        query = select(HabitCheckin).where(
            and_(
                HabitCheckin.habit_id == habit_id,
                HabitCheckin.check_date == check_date,
                HabitCheckin.time_slot == slot,
            )
        )
        return await self.session.scalar(query)

    async def get_checkins_for_date(self, user_id: int, target_date: date) -> list[HabitCheckin]:
        query = (
            select(HabitCheckin)
            .join(Habit, Habit.id == HabitCheckin.habit_id)
            .where(Habit.user_id == user_id, HabitCheckin.check_date == target_date)
            .order_by(HabitCheckin.created_at.asc())
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_checkins_for_range(
        self, user_id: int, start_date: date, end_date: date
    ) -> list[HabitCheckin]:
        query = (
            select(HabitCheckin)
            .join(Habit, Habit.id == HabitCheckin.habit_id)
            .where(
                Habit.user_id == user_id,
                HabitCheckin.check_date >= start_date,
                HabitCheckin.check_date <= end_date,
            )
            .order_by(HabitCheckin.check_date.asc(), HabitCheckin.created_at.asc())
        )
        result = await self.session.scalars(query)
        return list(result)

    async def delete_checkin(self, user_id: int, habit_id: int, check_date: date, slot: TimeSlot) -> bool:
        checkin = await self.get_checkin(
            user_id=user_id,
            habit_id=habit_id,
            check_date=check_date,
            slot=slot,
        )
        if checkin is None:
            return False
        await self.session.delete(checkin)
        await self.session.commit()
        return True
