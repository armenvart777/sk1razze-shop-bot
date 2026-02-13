from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
import aiosqlite

from keyboards.callbacks import ProfileCB
from keyboards.inline import profile_keyboard
from db.queries.users import get_user
from db.queries.texts import get_text_photo

router = Router(name="profile_info")


def _build_profile_text(user) -> str:
    balance = user["balance"]
    total_deposited = user["total_deposited"]
    balance_str = f"{int(balance)}" if balance == int(balance) else f"{balance:.2f}"
    deposited_str = f"{int(total_deposited)}" if total_deposited == int(total_deposited) else f"{total_deposited:.2f}"
    return (
        f"Ваш Профиль:\n"
        f"👤 Юзер: @{user['username'] or 'не указан'}\n"
        f"🆔 ID: {user['id']}\n"
        f"💰 Баланс: {balance_str}₽\n"
        f"💸 Всего пополнено: {deposited_str}₽\n"
        f"📅 Дата регистрации: {user['registered_at'][:16]}\n"
        f"👥 Рефералов: {user['referral_count']} чел"
    )


async def show_profile(message: Message, db: aiosqlite.Connection, user_id: int | None = None):
    uid = user_id or message.from_user.id
    user = await get_user(db, uid)
    if not user:
        await message.answer("Профиль не найден.")
        return
    kb = profile_keyboard()
    text = _build_profile_text(user)
    photo = await get_text_photo(db, "profile_template")
    if photo:
        try:
            await message.answer_photo(photo=photo, caption=text, reply_markup=kb)
        except Exception:
            await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def show_profile_cb(callback: CallbackQuery, db: aiosqlite.Connection):
    user = await get_user(db, callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return
    kb = profile_keyboard()
    text = _build_profile_text(user)
    photo = await get_text_photo(db, "profile_template")
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


@router.callback_query(ProfileCB.filter(F.action == "back"))
async def back_to_profile(callback: CallbackQuery, db: aiosqlite.Connection):
    user = await get_user(db, callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return
    kb = profile_keyboard()
    text = _build_profile_text(user)
    photo = await get_text_photo(db, "profile_template")
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
