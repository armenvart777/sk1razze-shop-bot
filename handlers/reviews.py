from aiogram.types import Message, CallbackQuery
import aiosqlite

from keyboards.inline import reviews_keyboard
from db.queries.texts import get_text_with_photo
from db.queries.settings import get_setting


async def show_reviews(message: Message, db: aiosqlite.Connection):
    text, photo = await get_text_with_photo(db, "reviews_text")
    url = await get_setting(db, "reviews_url") or ""
    kb = reviews_keyboard(reviews_url=url)
    if photo:
        try:
            await message.answer_photo(photo=photo, caption=text, reply_markup=kb)
        except Exception:
            await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def show_reviews_cb(callback: CallbackQuery, db: aiosqlite.Connection):
    text, photo = await get_text_with_photo(db, "reviews_text")
    url = await get_setting(db, "reviews_url") or ""
    kb = reviews_keyboard(reviews_url=url)
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)
    await callback.answer()
