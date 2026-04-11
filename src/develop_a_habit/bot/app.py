from aiogram import Dispatcher

from develop_a_habit.handlers.common import router as common_router


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(common_router)
    return dp
