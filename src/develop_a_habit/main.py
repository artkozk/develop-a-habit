import asyncio
import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.types import BotCommandScopeAllPrivateChats

from develop_a_habit.bot.app import setup_dispatcher
from develop_a_habit.config import get_settings
from develop_a_habit.jobs.transcription_queue import transcription_worker_loop
from develop_a_habit.jobs.weekly_digest import weekly_digest_loop
from develop_a_habit.logging_config import configure_logging


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    bot = Bot(token=settings.bot_token)
    dp = setup_dispatcher()

    # Interface is button-first: clear slash commands list in private chats.
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.delete_my_commands()

    weekly_task = asyncio.create_task(weekly_digest_loop(bot))
    transcription_task = asyncio.create_task(transcription_worker_loop(bot, settings))
    logger.info("Starting bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        weekly_task.cancel()
        transcription_task.cancel()
        with suppress(asyncio.CancelledError):
            await weekly_task
        with suppress(asyncio.CancelledError):
            await transcription_task


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
