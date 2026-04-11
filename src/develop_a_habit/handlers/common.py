from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="common")


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(
        "Привет! Бот Develop A Habit запущен.\n"
        "Дальше добавим полноценные inline-экраны и логику трекера."
    )
