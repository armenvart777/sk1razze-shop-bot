from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from keyboards.callbacks import ProfileCB
from keyboards.inline import admin_back_keyboard
from db.queries.users import get_user
from utils.referral import make_referral_link
from utils.formatting import format_price

router = Router(name="profile_referral")


@router.callback_query(ProfileCB.filter(F.action == "referral"))
async def show_referral(callback: CallbackQuery, db: aiosqlite.Connection):
    user = await get_user(db, callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    bot_me = await callback.bot.me()
    link = make_referral_link(bot_me.username, callback.from_user.id)

    text = (
        f"💎 Реферальная система\n\n"
        f"Ваша реферальная ссылка:\n{link}\n\n"
        f"👥 Приглашено: {user['referral_count']} чел.\n\n"
        f"Приглашайте друзей и получайте бонусы!"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=ProfileCB(action="back").pack(),
    ))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()
