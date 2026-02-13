from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from keyboards.callbacks import ProfileCB
from db.queries.promo import get_promo_by_code, has_user_used_promo, use_promo
from db.queries.users import update_balance
from states.user_states import PromoStates
from utils.formatting import format_price

router = Router(name="profile_promo")


@router.callback_query(ProfileCB.filter(F.action == "promo"))
async def ask_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.entering_code)
    await callback.message.edit_text(
        "🎟 Введите промокод:",
    )
    await callback.answer()


@router.message(PromoStates.entering_code)
async def process_promo(message: Message, db: aiosqlite.Connection, state: FSMContext):
    code = message.text.strip()
    promo = await get_promo_by_code(db, code)

    if not promo:
        await message.answer("❌ Промокод не найден или неактивен.")
        await state.clear()
        return

    if promo["current_uses"] >= promo["max_uses"]:
        await message.answer("❌ Промокод уже использован максимальное количество раз.")
        await state.clear()
        return

    used = await has_user_used_promo(db, promo["id"], message.from_user.id)
    if used:
        await message.answer("❌ Вы уже использовали этот промокод.")
        await state.clear()
        return

    # Apply promo — credit balance
    if promo["discount_type"] == "fixed":
        amount = promo["discount_value"]
        await update_balance(db, message.from_user.id, amount)
        await use_promo(db, promo["id"], message.from_user.id)
        await message.answer(f"✅ Промокод активирован! На баланс зачислено {format_price(amount)}")
    else:
        # Percent promo — store for next purchase
        await use_promo(db, promo["id"], message.from_user.id)
        await message.answer(f"✅ Промокод активирован! Скидка {promo['discount_value']}% на следующую покупку.")

    await state.clear()
