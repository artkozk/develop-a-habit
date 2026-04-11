import asyncio
import logging

from aiogram import Bot
from aiogram.types import BotCommandScopeAllPrivateChats

from develop_a_habit.bot.app import setup_dispatcher
from develop_a_habit.config import get_settings
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

    logger.info("Starting bot polling")
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
