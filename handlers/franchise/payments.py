from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchiseSbpCB
from db.queries.payments import get_payment, update_payment_status
from db.queries.users import update_balance, get_user
from utils.formatting import format_price
from config import settings
from services.bot_manager import get_main_bot

router = Router(name="franchise_payments")


async def _notify_admins_payment(bot: Bot, db: aiosqlite.Connection, payment: dict, action: str, franchise_owner_id: int):
    """Notify platform admins about franchise payment decisions."""
    user = await get_user(db, payment["user_id"])
    username = f"@{user['username']}" if user and user["username"] else str(payment["user_id"])
    owner = await get_user(db, franchise_owner_id)
    owner_name = f"@{owner['username']}" if owner and owner["username"] else str(franchise_owner_id)

    if action == "approve":
        emoji = "✅"
        status = "ПОДТВЕРЖДЁН"
    else:
        emoji = "❌"
        status = "ОТКЛОНЁН"

    text = (
        f"{emoji} Платёж франшизы {status}\n\n"
        f"🆔 Платёж #{payment['id']}\n"
        f"👤 Клиент: {username}\n"
        f"💰 Сумма: {format_price(payment['amount'])}\n"
        f"🏪 Франчайзи: {owner_name}\n"
        f"📋 Метод: {payment['method']}"
    )

    # Use main bot to notify admins (franchise bot can't message them)
    main_bot = get_main_bot() or bot
    for admin_id in settings.ADMIN_IDS:
        try:
            await main_bot.send_message(admin_id, text, parse_mode=None)
        except Exception:
            pass


@router.callback_query(FranchiseSbpCB.filter(F.action == "approve"), IsFranchiseOwner())
async def franchise_sbp_approve(
    callback: CallbackQuery, callback_data: FranchiseSbpCB,
    db: aiosqlite.Connection, bot: Bot,
):
    payment = await get_payment(db, callback_data.payment_id)
    if not payment:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    if payment["status"] == "paid":
        await callback.answer("Этот платеж уже подтвержден", show_alert=True)
        return

    await update_payment_status(db, callback_data.payment_id, "paid")
    await update_balance(db, payment["user_id"], payment["amount"])

    caption = callback.message.caption or ""
    try:
        await callback.message.edit_caption(
            caption=caption + f"\n\n✅ ПОДТВЕРЖДЕНО владельцем франшизы"
        )
    except Exception:
        pass
    await callback.answer("✅ Платеж подтвержден", show_alert=True)

    try:
        await bot.send_message(
            payment["user_id"],
            f"✅ Ваш СБП-платеж #{callback_data.payment_id} подтвержден!\n"
            f"💰 Зачислено: {format_price(payment['amount'])}"
        )
    except Exception:
        pass

    await _notify_admins_payment(bot, db, payment, "approve", callback.from_user.id)


@router.callback_query(FranchiseSbpCB.filter(F.action == "reject"), IsFranchiseOwner())
async def franchise_sbp_reject(
    callback: CallbackQuery, callback_data: FranchiseSbpCB,
    db: aiosqlite.Connection, bot: Bot,
):
    payment = await get_payment(db, callback_data.payment_id)
    if not payment:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    if payment["status"] == "paid":
        await callback.answer("Этот платеж уже подтвержден", show_alert=True)
        return

    await update_payment_status(db, callback_data.payment_id, "cancelled")

    caption = callback.message.caption or ""
    try:
        await callback.message.edit_caption(
            caption=caption + f"\n\n❌ ОТКЛОНЕНО владельцем франшизы"
        )
    except Exception:
        pass
    await callback.answer("❌ Платеж отклонен", show_alert=True)

    try:
        await bot.send_message(
            payment["user_id"],
            f"❌ Ваш СБП-платеж #{callback_data.payment_id} отклонен.\n"
            f"Обратитесь в поддержку."
        )
    except Exception:
        pass

    await _notify_admins_payment(bot, db, payment, "reject", callback.from_user.id)
