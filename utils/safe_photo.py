from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest


async def answer_photo_safe(target: Message | CallbackQuery, photo: str, caption: str, reply_markup=None, parse_mode=None):
    """Send photo with fallback to text if file_id is invalid (cross-bot issue)."""
    msg = target if isinstance(target, Message) else target.message
    try:
        await msg.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        await msg.answer(caption or "—", reply_markup=reply_markup, parse_mode=parse_mode)
