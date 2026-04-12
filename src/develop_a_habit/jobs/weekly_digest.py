from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from develop_a_habit.db.models import WeeklyPrompt
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.jobs.schedule_utils import is_weekly_digest_due
from develop_a_habit.services import build_services

logger = logging.getLogger(__name__)


def _week_start(target: date) -> date:
    return target - timedelta(days=target.weekday())


def _encode_day(day: date) -> str:
    return day.strftime("%Y%m%d")


async def send_weekly_digest_if_due(bot: Bot) -> None:
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        users = await services.user_service.list_users()

        for user in users:
            try:
                tz = ZoneInfo(user.timezone)
            except ZoneInfoNotFoundError:
                tz = ZoneInfo("Europe/Moscow")

            local_now = now_utc.astimezone(tz)
            if not is_weekly_digest_due(local_now):
                continue

            week_start = _week_start(local_now.date())
            week_end = week_start + timedelta(days=6)
            already_sent = await session.scalar(
                select(WeeklyPrompt).where(
                    WeeklyPrompt.user_id == user.id,
                    WeeklyPrompt.week_start == week_start,
                )
            )
            if already_sent is not None:
                continue

            metrics = await services.metrics_service.compute_period_metrics(
                user_id=user.id,
                start_date=week_start,
                end_date=week_end,
                today=local_now.date(),
            )
            habit_progress = await services.metrics_service.compute_habit_progress(
                user_id=user.id,
                start_date=week_start,
                end_date=week_end,
                today=local_now.date(),
            )

            text = (
                f"Итоги недели {week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}\n"
                f"Плановые слоты: {metrics.plan_slots}\n"
                f"Выполнено: {metrics.completed_slots}\n"
                f"Сверх плана: {metrics.extra_slots}\n"
                f"Выполнение плана: {metrics.plan_completion}%\n"
                f"С учетом сверх плана: {metrics.over_completion}%\n\n"
                "По каждой привычке:\n"
            )
            habit_lines: list[str] = []
            for item in habit_progress:
                icon = f"{item.icon_emoji} " if item.icon_emoji else ""
                goal_part = ""
                if item.goal_days is not None and item.goal_days > 0:
                    marker = " ✅" if item.goal_reached else ""
                    goal_part = (
                        f", цель {item.goal_progress_days}/{item.goal_days}{marker}, "
                        f"циклов {item.goal_completed_cycles}"
                    )
                habit_lines.append(
                    (
                        f"- {icon}{item.name}: {item.weekly_success_days}/{item.weekly_due_days} дн, "
                        f"держитесь {item.current_streak_days} дн подряд{goal_part}"
                    )
                )
            if not habit_lines:
                habit_lines.append("- Пока нет активных привычек")

            text = (
                text
                + "\n".join(habit_lines)
                + "\n\nКак прошла неделя? Нажмите кнопку ниже и отправьте комментарий."
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📝 Прокомментировать неделю",
                            callback_data=f"weekly:comment:{_encode_day(week_start)}",
                        )
                    ]
                ]
            )

            try:
                await bot.send_message(user.telegram_user_id, text=text, reply_markup=keyboard)
                session.add(WeeklyPrompt(user_id=user.id, week_start=week_start))
                await session.commit()
            except Exception:
                logger.exception("Failed to send weekly digest to telegram user %s", user.telegram_user_id)
                await session.rollback()


async def weekly_digest_loop(bot: Bot, interval_seconds: int = 60) -> None:
    while True:
        try:
            await send_weekly_digest_if_due(bot)
        except Exception:
            logger.exception("Weekly digest loop iteration failed")
        await asyncio.sleep(interval_seconds)
