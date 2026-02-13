from aiogram.types import Message, CallbackQuery
import aiosqlite

from keyboards.inline import support_keyboard
from db.queries.texts import get_text, get_text_photo
from db.queries.settings import get_setting


async def show_support(message: Message, db: aiosqlite.Connection):
    text = await get_text(db, "support_text")
    photo = await get_text_photo(db, "support_text")
    bold_text = f"💎 <b>{text}</b>"
    url = await get_setting(db, "support_url") or ""
    kb = support_keyboard(support_url=url)
    if photo:
        try:
            await message.answer_photo(photo=photo, caption=bold_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await message.answer(bold_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(bold_text, reply_markup=kb, parse_mode="HTML")


async def show_support_cb(callback: CallbackQuery, db: aiosqlite.Connection):
    text = await get_text(db, "support_text")
    photo = await get_text_photo(db, "support_text")
    bold_text = f"💎 <b>{text}</b>"
    url = await get_setting(db, "support_url") or ""
    kb = support_keyboard(support_url=url)
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=photo, caption=bold_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(bold_text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(bold_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(bold_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
