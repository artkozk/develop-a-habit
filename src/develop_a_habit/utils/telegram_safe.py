from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return False
        raise


async def safe_edit_reply_markup(
    message: Message,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return False
        raise
