from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import build_services

router = Router(name="stats")


def _period_range(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "year":
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
        return start, end

    if period == "month":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start, end

    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _stats_keyboard(period: str) -> InlineKeyboardMarkup:
    def label(name: str, value: str) -> str:
        marker = "•" if period == value else ""
        return f"{name} {marker}".strip()

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label("Неделя", "week"), callback_data="stats:period:week"),
                InlineKeyboardButton(text=label("Месяц", "month"), callback_data="stats:period:month"),
                InlineKeyboardButton(text=label("Год", "year"), callback_data="stats:period:year"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:submenu:analytics")],
        ]
    )


async def _render_stats(target: Message | CallbackQuery, telegram_user_id: int, period: str) -> None:
    start, end = _period_range(period)
    settings = get_settings()

    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        metrics = await services.metrics_service.compute_period_metrics(
            user_id=user.id,
            start_date=start,
            end_date=end,
        )

    text = (
        f"Статистика ({period})\n"
        f"Период: {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}\n\n"
        f"Плановые слоты: {metrics.plan_slots}\n"
        f"Выполнено: {metrics.completed_slots}\n"
        f"Сверх плана (выходные): {metrics.extra_slots}\n"
        f"Выполнение плана: {metrics.plan_completion}%\n"
        f"С учетом сверх плана: {metrics.over_completion}%"
    )

    keyboard = _stats_keyboard(period)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("stats:period:"))
async def stats_period(callback: CallbackQuery) -> None:
    await callback.answer()
    period = callback.data.split(":")[-1]
    if period not in {"week", "month", "year"}:
        await callback.message.answer("Неверный период")
        return
    await _render_stats(callback, telegram_user_id=callback.from_user.id, period=period)
