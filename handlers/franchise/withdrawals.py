from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchisePanelCB, WithdrawalCB
from db.queries.users import get_user
from db.queries.withdrawals import (
    create_withdrawal, get_user_withdrawals, has_pending_withdrawal,
)
from utils.formatting import format_price
from config import settings
from services.bot_manager import get_main_bot

router = Router(name="franchise_withdrawals")

MIN_WITHDRAWAL = 500


class WithdrawalStates(StatesGroup):
    waiting_amount = State()
    waiting_details = State()


@router.callback_query(FranchisePanelCB.filter(F.action == "withdrawal"), IsFranchiseOwner())
async def withdrawal_menu(
    callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict, state: FSMContext,
):
    await state.clear()
    user = await get_user(db, franchise["owner_id"])
    balance = user["balance"] if user else 0

    has_pending = await has_pending_withdrawal(db, franchise["owner_id"])
    history = await get_user_withdrawals(db, franchise["owner_id"], limit=5)

    lines = [
        f"💸 Вывод средств\n",
        f"💰 Ваш баланс: {format_price(balance)}",
        f"📌 Минимальная сумма: {format_price(MIN_WITHDRAWAL)}\n",
    ]

    if has_pending:
        lines.append("⏳ У вас есть заявка на рассмотрении.\n")

    if history:
        lines.append("📋 Последние заявки:")
        for w in history:
            status_map = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
            s = status_map.get(w["status"], "❓")
            date = (w["created_at"] or "")[:16]
            lines.append(f"  {s} {format_price(w['amount'])} — {date}")

    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    if balance >= MIN_WITHDRAWAL and not has_pending:
        kb.row(InlineKeyboardButton(
            text="💸 Создать заявку",
            callback_data=WithdrawalCB(action="create").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(WithdrawalCB.filter(F.action == "create"), IsFranchiseOwner())
async def start_withdrawal(callback: CallbackQuery, state: FSMContext, franchise: dict):
    await state.set_state(WithdrawalStates.waiting_amount)
    await state.update_data(franchise_id=franchise["id"], owner_id=franchise["owner_id"])
    try:
        await callback.message.edit_text(
            f"💸 Введите сумму вывода (минимум {format_price(MIN_WITHDRAWAL)}):"
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            f"💸 Введите сумму вывода (минимум {format_price(MIN_WITHDRAWAL)}):"
        )
    await callback.answer()


@router.message(WithdrawalStates.waiting_amount, IsFranchiseOwner())
async def process_amount(message: Message, db: aiosqlite.Connection, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < MIN_WITHDRAWAL:
            await message.answer(f"Минимальная сумма: {format_price(MIN_WITHDRAWAL)}")
            return
    except (ValueError, AttributeError):
        await message.answer("Введите корректную сумму:")
        return

    data = await state.get_data()
    user = await get_user(db, data["owner_id"])
    if not user or user["balance"] < amount:
        await message.answer("Недостаточно средств на балансе.")
        await state.clear()
        return

    await state.update_data(amount=amount)
    await state.set_state(WithdrawalStates.waiting_details)
    await message.answer(
        "Введите реквизиты для вывода (номер карты, кошелёк и т.д.):"
    )


@router.message(WithdrawalStates.waiting_details, IsFranchiseOwner())
async def process_details(message: Message, db: aiosqlite.Connection, state: FSMContext):
    details = message.text.strip() if message.text else ""
    if not details:
        await message.answer("Введите реквизиты:")
        return

    data = await state.get_data()
    amount = data["amount"]
    franchise_id = data["franchise_id"]
    owner_id = data["owner_id"]

    # Verify balance again
    user = await get_user(db, owner_id)
    if not user or user["balance"] < amount:
        await message.answer("Недостаточно средств на балансе.")
        await state.clear()
        return

    # Deduct balance immediately (will be refunded if rejected)
    await db.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
        (amount, owner_id, amount),
    )
    cursor = await db.execute("SELECT changes()")
    changes = (await cursor.fetchone())[0]
    if changes == 0:
        await message.answer("Недостаточно средств на балансе.")
        await state.clear()
        return

    await db.commit()

    # Create withdrawal request
    wd_id = await create_withdrawal(db, franchise_id, owner_id, amount, details)

    await state.clear()
    await message.answer(
        f"✅ Заявка на вывод #{wd_id} создана!\n\n"
        f"💰 Сумма: {format_price(amount)}\n"
        f"📋 Реквизиты: {details}\n\n"
        f"Ожидайте одобрения администратора."
    )

    # Notify admins
    from db.queries.franchises import get_franchise
    franchise = await get_franchise(db, franchise_id)
    franchise_name = franchise["name"] if franchise else f"ID:{franchise_id}"
    username = f"@{user['username']}" if user["username"] else str(owner_id)

    admin_text = (
        f"💸 Новая заявка на вывод #{wd_id}\n\n"
        f"🏪 Франшиза: {franchise_name}\n"
        f"👤 Владелец: {username}\n"
        f"💰 Сумма: {format_price(amount)}\n"
        f"📋 Реквизиты: {details}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=WithdrawalCB(id=wd_id, action="approve").pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=WithdrawalCB(id=wd_id, action="reject").pack(),
        ),
    )

    # Use main bot to notify admins (franchise bot can't message them)
    main_bot = get_main_bot() or message.bot
    for admin_id in settings.ADMIN_IDS:
        try:
            await main_bot.send_message(admin_id, admin_text, reply_markup=kb.as_markup(), parse_mode=None)
        except Exception:
            pass
