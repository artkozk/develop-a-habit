from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="common")


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(
        "Привет! Develop A Habit запущен.\n"
        "Основные команды:\n"
        "/today — ближайшие привычки\n"
        "/habits — управление привычками\n"
        "/calendar — календарь недели\n"
        "/diary — дневник\n"
        "/search_notes — поиск заметок\n"
        "/stats — статистика\n"
        "/export_diary — экспорт дневника\n"
        "/export_stats_html — HTML статистика"
    )
