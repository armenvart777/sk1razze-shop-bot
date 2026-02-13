from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminProductCB
from keyboards.inline import admin_back_keyboard
from db.queries.products import get_product, get_product_items, add_product_items, delete_unsold_items, update_stock_count
from states.admin_states import AdminItemStates

router = Router(name="admin_product_items")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminProductCB.filter(F.action == "items"))
async def show_items(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    items = await get_product_items(db, callback_data.id)
    available = sum(1 for i in items if not i["is_sold"])
    sold = sum(1 for i in items if i["is_sold"])

    text = (
        f"📋 Stock товара: {product['name']}\n\n"
        f"✅ Доступно: {available}\n"
        f"📦 Продано: {sold}\n"
        f"📊 Всего: {len(items)}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="➕ Добавить товары",
        callback_data=f"add_items:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить непроданные",
        callback_data=f"del_items:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="📋 Показать содержимое",
        callback_data=f"show_items:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminProductCB(id=callback_data.id, action="view").pack(),
    ))

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("add_items:"))
async def start_add_items(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split(":")[1])
    await state.set_state(AdminItemStates.waiting_content)
    await state.update_data(prod_id=prod_id, items_added=0)
    await callback.message.edit_text(
        "Отправляйте содержимое товаров (по одному сообщению на единицу).\n"
        "Или отправьте несколько строк — каждая строка станет отдельным товаром.\n\n"
        "Когда закончите, отправьте /done"
    )
    await callback.answer()


@router.message(AdminItemStates.waiting_content)
async def process_items(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if message.text and message.text.strip() == "/done":
        data = await state.get_data()
        prod_id = data["prod_id"]
        count = data.get("items_added", 0)
        await update_stock_count(db, prod_id)
        await state.clear()
        product = await get_product(db, prod_id)
        await message.answer(
            f"✅ Добавлено {count} единиц.\n"
            f"📊 В наличии: {product['stock_count']} шт."
        )
        return

    data = await state.get_data()
    prod_id = data["prod_id"]

    if message.text:
        lines = message.text.strip().split("\n")
        count = await add_product_items(db, prod_id, lines)
        total = data.get("items_added", 0) + count
        await state.update_data(items_added=total)
        await message.answer(f"✅ +{count} единиц (всего добавлено: {total}). Продолжайте или /done")
    else:
        await message.answer("Отправьте текстовое содержимое.")


@router.callback_query(F.data.startswith("del_items:"))
async def delete_items(callback: CallbackQuery, db: aiosqlite.Connection):
    prod_id = int(callback.data.split(":")[1])
    count = await delete_unsold_items(db, prod_id)
    await callback.answer(f"Удалено {count} непроданных единиц", show_alert=True)

    # Refresh
    product = await get_product(db, prod_id)
    items = await get_product_items(db, prod_id)
    available = sum(1 for i in items if not i["is_sold"])
    sold = sum(1 for i in items if i["is_sold"])
    text = (
        f"📋 Stock товара: {product['name']}\n\n"
        f"✅ Доступно: {available}\n"
        f"📦 Продано: {sold}\n"
        f"📊 Всего: {len(items)}"
    )
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Добавить товары", callback_data=f"add_items:{prod_id}"))
    kb.row(InlineKeyboardButton(text="🗑 Удалить непроданные", callback_data=f"del_items:{prod_id}"))
    kb.row(InlineKeyboardButton(text="📋 Показать содержимое", callback_data=f"show_items:{prod_id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminProductCB(id=prod_id, action="view").pack()))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("show_items:"))
async def show_item_contents(callback: CallbackQuery, db: aiosqlite.Connection):
    prod_id = int(callback.data.split(":")[1])
    items = await get_product_items(db, prod_id)

    if not items:
        await callback.answer("Нет товаров в stock", show_alert=True)
        return

    text_parts = []
    for i, item in enumerate(items[:20], 1):
        status = "🟢" if not item["is_sold"] else "🔴"
        content = item["content"][:50] + "..." if len(item["content"]) > 50 else item["content"]
        text_parts.append(f"{i}. {status} {content}")

    text = "📋 Содержимое (первые 20):\n\n" + "\n".join(text_parts)
    if len(items) > 20:
        text += f"\n\n... и ещё {len(items) - 20}"

    await callback.message.answer(text)
    await callback.answer()
