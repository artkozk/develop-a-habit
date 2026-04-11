from aiogram import Dispatcher

from develop_a_habit.handlers.calendar import router as calendar_router
from develop_a_habit.handlers.common import router as common_router
from develop_a_habit.handlers.diary import router as diary_router
from develop_a_habit.handlers.export import router as export_router
from develop_a_habit.handlers.habits import router as habits_router
from develop_a_habit.handlers.search_notes import router as search_notes_router
from develop_a_habit.handlers.settings import router as settings_router
from develop_a_habit.handlers.stats import router as stats_router
from develop_a_habit.handlers.weekly import router as weekly_router


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(common_router)
    dp.include_router(habits_router)
    dp.include_router(calendar_router)
    dp.include_router(diary_router)
    dp.include_router(export_router)
    dp.include_router(search_notes_router)
    dp.include_router(settings_router)
    dp.include_router(stats_router)
    dp.include_router(weekly_router)
    return dp
