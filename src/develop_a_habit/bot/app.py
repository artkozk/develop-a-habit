from aiogram import Dispatcher

from develop_a_habit.handlers.calendar import router as calendar_router
from develop_a_habit.handlers.common import router as common_router
from develop_a_habit.handlers.habits import router as habits_router
from develop_a_habit.handlers.stats import router as stats_router


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(common_router)
    dp.include_router(habits_router)
    dp.include_router(calendar_router)
    dp.include_router(stats_router)
    return dp
