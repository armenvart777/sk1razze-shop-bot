from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB
from keyboards.inline import admin_back_keyboard
from db.queries.statistics import get_stats
from utils.formatting import format_price

router = Router(name="admin_statistics")
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "stats"))
async def show_stats(callback: CallbackQuery, db: aiosqlite.Connection):
    stats = await get_stats(db)
    text = (
        f"📊 Статистика\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"👤 Новые (24ч): {stats['new_users_24h']}\n"
        f"👤 Новые (7д): {stats['new_users_7d']}\n\n"
        f"📋 Всего заказов: {stats['total_orders']}\n"
        f"📋 Заказы (24ч): {stats['orders_24h']}\n\n"
        f"💰 Выручка (24ч): {format_price(stats['revenue_24h'])}\n"
        f"💰 Выручка (7д): {format_price(stats['revenue_7d'])}\n"
        f"💰 Выручка (всего): {format_price(stats['total_revenue'])}\n\n"
        f"💸 Депозитов: {format_price(stats['total_deposited'])}\n"
        f"🎟 Активных промокодов: {stats['active_promos']}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Обновить", callback_data=AdminPanelCB(section="stats").pack()))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()
