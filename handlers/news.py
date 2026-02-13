from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

from keyboards.callbacks import MainMenuCB
from db.queries.texts import get_text_with_photo
from db.queries.settings import get_setting
from config import settings


async def _get_channel_url(db: aiosqlite.Connection) -> str:
    username = await get_setting(db, "channel_username") or settings.CHANNEL_USERNAME
    if not username:
        return ""
    username = username.lstrip("@")
    return f"https://t.me/{username}"


async def show_news(message: Message, db: aiosqlite.Connection):
    text, photo = await get_text_with_photo(db, "news_text")
    url = await _get_channel_url(db)

    kb = InlineKeyboardBuilder()
    if url:
        kb.row(InlineKeyboardButton(text="📢 Новостной канал", url=url))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))

    if photo:
        try:
            await message.answer_photo(
                photo=photo, caption=text, reply_markup=kb.as_markup(),
            )
        except Exception:
            await message.answer(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())


async def show_news_cb(callback: CallbackQuery, db: aiosqlite.Connection):
    text, photo = await get_text_with_photo(db, "news_text")
    url = await _get_channel_url(db)

    kb = InlineKeyboardBuilder()
    if url:
        kb.row(InlineKeyboardButton(text="📢 Новостной канал", url=url))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))

    try:
        await callback.message.delete()
    except Exception:
        pass

    if photo:
        try:
            await callback.message.answer_photo(
                photo=photo, caption=text, reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())
    else:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
