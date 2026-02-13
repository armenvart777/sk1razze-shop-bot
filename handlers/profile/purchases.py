from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from keyboards.callbacks import ProfileCB, OrderCB, PaginationCB
from keyboards.inline import orders_keyboard
from db.queries.orders import get_user_orders, get_order, get_user_order_count
from utils.formatting import format_price

router = Router(name="profile_purchases")


@router.callback_query(ProfileCB.filter(F.action == "purchases"))
async def show_purchases(callback: CallbackQuery, db: aiosqlite.Connection):
    orders = await get_user_orders(db, callback.from_user.id)
    if not orders:
        await callback.answer("У вас пока нет покупок", show_alert=True)
        return

    kb = orders_keyboard(orders)
    try:
        await callback.message.edit_text("⭐ Ваши последние покупки:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("⭐ Ваши последние покупки:", reply_markup=kb)
    await callback.answer()


@router.callback_query(OrderCB.filter(F.action == "view"))
async def view_order(callback: CallbackQuery, callback_data: OrderCB, db: aiosqlite.Connection):
    order = await get_order(db, callback_data.id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    name = order["product_name"] or "Удалённый товар"
    text = (
        f"📋 Заказ #{order['id']}\n\n"
        f"📦 Товар: {name}\n"
        f"💰 Сумма: {format_price(order['total_price'])}\n"
        f"📅 Дата: {order['created_at'][:16]}\n"
        f"📊 Статус: {order['status']}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад к покупкам",
        callback_data=ProfileCB(action="purchases").pack(),
    ))
    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(PaginationCB.filter(F.target == "orders"))
async def paginate_orders(callback: CallbackQuery, callback_data: PaginationCB, db: aiosqlite.Connection):
    orders = await get_user_orders(db, callback.from_user.id, offset=callback_data.page * 5, limit=50)
    kb = orders_keyboard(orders, page=callback_data.page)
    try:
        await callback.message.edit_text("⭐ Ваши последние покупки:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("⭐ Ваши последние покупки:", reply_markup=kb)
    await callback.answer()
