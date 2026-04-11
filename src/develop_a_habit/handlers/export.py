from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from develop_a_habit.config import get_settings
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import ExportService, StatsReportService, build_services

router = Router(name="export")


async def export_diary_message(message: Message) -> None:
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


async def export_stats_html_message(message: Message) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=message.from_user.id,
            timezone=settings.timezone_default,
        )
        report_service = StatsReportService(session)
        result = await report_service.generate_yearly_html(
            user_id=user.id,
            telegram_user_id=message.from_user.id,
        )

    await message.answer_document(
        FSInputFile(result.file_path),
        caption="HTML-отчет по статистике готов",
    )


@router.callback_query(F.data == "export:diary")
async def export_diary_callback(callback: CallbackQuery) -> None:
    await callback.answer("Формирую архив...")
    await export_diary_message(callback.message)


@router.callback_query(F.data == "export:stats_html")
async def export_stats_html_callback(callback: CallbackQuery) -> None:
    await callback.answer("Готовлю HTML...")
    await export_stats_html_message(callback.message)
