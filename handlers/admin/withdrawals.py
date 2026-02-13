from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import WithdrawalCB
from db.queries.withdrawals import get_withdrawal, update_withdrawal_status
from db.queries.users import update_balance
from utils.formatting import format_price

router = Router(name="admin_withdrawals")
router.callback_query.filter(IsAdmin())


@router.callback_query(WithdrawalCB.filter(F.action == "approve"))
async def approve_withdrawal(
    callback: CallbackQuery, callback_data: WithdrawalCB, db: aiosqlite.Connection,
):
    wd = await get_withdrawal(db, callback_data.id)
    if not wd:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if wd["status"] != "pending":
        await callback.answer(f"Заявка уже обработана ({wd['status']})", show_alert=True)
        return

    await update_withdrawal_status(db, wd["id"], "approved")

    # Update admin message
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ Одобрено администратором {callback.from_user.first_name}"
        )
    except Exception:
        pass

    await callback.answer("Заявка одобрена", show_alert=True)

    # Notify franchise owner
    try:
        await callback.bot.send_message(
            wd["user_id"],
            f"✅ Ваша заявка на вывод #{wd['id']} одобрена!\n\n"
            f"💰 Сумма: {format_price(wd['amount'])}\n"
            f"📋 Реквизиты: {wd['details']}\n\n"
            f"Средства будут отправлены в ближайшее время."
        )
    except Exception:
        pass


@router.callback_query(WithdrawalCB.filter(F.action == "reject"))
async def reject_withdrawal(
    callback: CallbackQuery, callback_data: WithdrawalCB, db: aiosqlite.Connection,
):
    wd = await get_withdrawal(db, callback_data.id)
    if not wd:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if wd["status"] != "pending":
        await callback.answer(f"Заявка уже обработана ({wd['status']})", show_alert=True)
        return

    # Refund balance
    await update_balance(db, wd["user_id"], wd["amount"])

    await update_withdrawal_status(db, wd["id"], "rejected")

    # Update admin message
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ Отклонено администратором {callback.from_user.first_name}"
        )
    except Exception:
        pass

    await callback.answer("Заявка отклонена, баланс возвращён", show_alert=True)

    # Notify franchise owner
    try:
        await callback.bot.send_message(
            wd["user_id"],
            f"❌ Ваша заявка на вывод #{wd['id']} отклонена.\n\n"
            f"💰 Сумма {format_price(wd['amount'])} возвращена на баланс."
        )
    except Exception:
        pass
