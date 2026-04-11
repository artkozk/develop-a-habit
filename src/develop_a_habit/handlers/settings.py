from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from develop_a_habit.config import get_settings
from develop_a_habit.db.models import DayOffRule
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import build_services

router = Router(name="settings")

WEEKDAYS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}


def _settings_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for weekday in range(7):
        marker = "✅ " if weekday in selected else ""
        row.append(
            InlineKeyboardButton(
                text=f"{marker}{WEEKDAYS[weekday]}",
                callback_data=f"settings:dayoff:toggle:{weekday}",
            )
        )
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="💾 Сохранить выходные", callback_data="settings:dayoff:save")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _load_weekday_dayoffs(telegram_user_id: int) -> tuple[int, set[int]]:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=telegram_user_id,
            timezone=settings.timezone_default,
        )
        query = select(DayOffRule).where(DayOffRule.user_id == user.id, DayOffRule.weekday.is_not(None))
        rules = list(await session.scalars(query))
        selected = {rule.weekday for rule in rules if rule.weekday is not None}
        return user.id, selected


@router.message(Command("settings"))
async def settings_menu(message: Message) -> None:
    user_id, selected = await _load_weekday_dayoffs(message.from_user.id)
    _ = user_id
    await message.answer(
        "Настройки выходных. Выберите дни недели, которые считаются выходными:",
        reply_markup=_settings_keyboard(selected),
    )


@router.callback_query(F.data.startswith("settings:dayoff:toggle:"))
async def settings_toggle_dayoff(callback: CallbackQuery) -> None:
    weekday = int(callback.data.split(":")[-1])
    _, selected = await _load_weekday_dayoffs(callback.from_user.id)

    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)

    await callback.message.edit_reply_markup(reply_markup=_settings_keyboard(selected))
    await callback.answer()


@router.callback_query(F.data == "settings:dayoff:save")
async def settings_save_dayoff(callback: CallbackQuery) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        user = await services.user_service.get_or_create_by_telegram_id(
            telegram_user_id=callback.from_user.id,
            timezone=settings.timezone_default,
        )
        selected = set()
        if callback.message.reply_markup:
            for row in callback.message.reply_markup.inline_keyboard:
                for button in row:
                    if button.callback_data and button.callback_data.startswith("settings:dayoff:toggle:"):
                        prefix = "✅ "
                        if button.text.startswith(prefix):
                            selected.add(int(button.callback_data.split(":")[-1]))

        await services.habit_service.replace_day_off_weekdays(user.id, sorted(selected))

    await callback.answer("Выходные сохранены")
    await callback.message.answer("Настройки выходных обновлены ✅")
