from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, PaginationCB
from keyboards.inline import admin_back_keyboard
from db.queries.orders import get_all_orders, get_order, get_order_count
from utils.formatting import format_price
from utils.pagination import paginate, add_pagination_row

router = Router(name="admin_orders")
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "orders"))
async def show_orders(callback: CallbackQuery, db: aiosqlite.Connection):
    await _show_orders_page(callback, db, 0)
    await callback.answer()


@router.callback_query(PaginationCB.filter(F.target == "aorders"))
async def paginate_orders(callback: CallbackQuery, callback_data: PaginationCB, db: aiosqlite.Connection):
    await _show_orders_page(callback, db, callback_data.page)
    await callback.answer()


async def _show_orders_page(callback: CallbackQuery, db: aiosqlite.Connection, page: int):
    total = await get_order_count(db)
    orders = await get_all_orders(db, offset=page * 10, limit=10)

    if not orders:
        await callback.message.edit_text("📋 Заказов пока нет.", reply_markup=admin_back_keyboard("main"))
        return

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    text_parts = ["📋 Заказы:\n"]
    for o in orders:
        name = o["product_name"] or "—"
        username = o["username"] or "—"
        text_parts.append(
            f"#{o['id']} | @{username} | {name} | {format_price(o['total_price'])} | {o['created_at'][:10]}"
        )

    total_pages = max(1, (total + 9) // 10)
    has_prev = page > 0
    has_next = page < total_pages - 1
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "aorders")
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))

    await callback.message.edit_text("\n".join(text_parts), reply_markup=kb.as_markup())
