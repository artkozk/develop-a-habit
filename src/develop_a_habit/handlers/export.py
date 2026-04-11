from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import ExportService, build_services

router = Router(name="export")


@router.message(Command("export_diary"))
async def export_diary(message: Message) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        export_service = ExportService(session)
        result = await export_service.export_diary_zip(bot=message.bot, user_id=user.id)

    await message.answer_document(
        FSInputFile(result.archive_path),
        caption=f"Экспорт готов. Записей: {result.entries_count}",
    )
