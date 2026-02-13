from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchisePanelCB, FranchiseOrderCB
from db.queries.orders import get_franchise_orders, get_franchise_order_count, get_order
from utils.formatting import format_price

router = Router(name="franchise_orders")


@router.callback_query(FranchisePanelCB.filter(F.action == "orders"), IsFranchiseOwner())
async def show_orders(
    callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict,
):
    await _show_orders_page(callback, db, franchise, 0)


@router.callback_query(F.data.startswith("ford_page:"), IsFranchiseOwner())
async def orders_page(
    callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict,
):
    page = int(callback.data.split(":")[1])
    await _show_orders_page(callback, db, franchise, page)


async def _show_orders_page(
    callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict, page: int,
):
    per_page = 10
    offset = page * per_page
    total = await get_franchise_order_count(db, franchise["id"])
    orders = await get_franchise_orders(db, franchise["id"], offset=offset, limit=per_page)

    if not orders and page == 0:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=FranchisePanelCB(action="back").pack(),
        ))
        try:
            await callback.message.edit_text(
                "📋 Заказы франшизы\n\nЗаказов пока нет.",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                "📋 Заказы франшизы\n\nЗаказов пока нет.",
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
        return

    total_pages = max(1, (total + per_page - 1) // per_page)
    lines = [f"📋 Заказы франшизы (стр. {page + 1}/{total_pages}, всего {total}):\n"]

    for o in orders:
        product_name = o["product_name"] or "Удален"
        username = f"@{o['username']}" if o["username"] else str(o["user_id"])
        date_str = (o["created_at"] or "")[:16]
        lines.append(
            f"  #{o['id']} | {product_name} | {format_price(o['total_price'])}\n"
            f"  👤 {username} | 📅 {date_str}"
        )

    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ford_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ford_page:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(
        text="◀️ В панель",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
