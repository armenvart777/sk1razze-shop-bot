from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPrivateChannelCB, AdminPanelCB
from db.queries.private_channels import (
    get_all_channels, get_channel, create_channel,
    update_channel, delete_channel, get_channel_subscriptions,
)
from db.queries.products import create_product, update_product, delete_product
from db.queries.categories import get_all_root_categories, get_all_subcategories
from utils.formatting import format_price

router = Router(name="admin_private_channels")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AdminPrivChStates(StatesGroup):
    waiting_name = State()
    waiting_channel_id = State()
    waiting_price = State()
    waiting_duration = State()
    waiting_description = State()
    waiting_category = State()


@router.callback_query(AdminPanelCB.filter(F.section == "private_channels"))
async def show_channels(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    channels = await get_all_channels(db)

    kb = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch["is_active"] else "❌"
        kb.row(InlineKeyboardButton(
            text=f"{status} {ch['name']} — {format_price(ch['price'])} / {ch['duration_days']}д",
            callback_data=AdminPrivateChannelCB(id=ch["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="➕ Добавить приватку",
        callback_data=AdminPrivateChannelCB(id=0, action="add").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="main").pack(),
    ))

    try:
        await callback.message.edit_text(
            "🔐 Управление приватками:", reply_markup=kb.as_markup(),
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "🔐 Управление приватками:", reply_markup=kb.as_markup(),
        )
    await callback.answer()


@router.callback_query(AdminPrivateChannelCB.filter(F.action == "view"))
async def view_channel(
    callback: CallbackQuery, callback_data: AdminPrivateChannelCB, db: aiosqlite.Connection,
):
    ch = await get_channel(db, callback_data.id)
    if not ch:
        await callback.answer("Канал не найден", show_alert=True)
        return

    subs = await get_channel_subscriptions(db, ch["id"])
    status = "Активен" if ch["is_active"] else "Отключен"

    text = (
        f"🔐 {ch['name']}\n\n"
        f"📝 {ch['description'] or 'Без описания'}\n"
        f"💰 Цена: {format_price(ch['price'])}\n"
        f"📅 Срок: {ch['duration_days']} дней\n"
        f"📊 Статус: {status}\n"
        f"👥 Активных подписок: {len(subs)}\n"
        f"🆔 Channel ID: {ch['channel_id']}"
    )
    if ch["product_id"]:
        text += f"\n📦 Товар ID: {ch['product_id']}"

    kb = InlineKeyboardBuilder()
    toggle_text = "⏸ Отключить" if ch["is_active"] else "▶️ Включить"
    kb.row(InlineKeyboardButton(
        text=toggle_text,
        callback_data=AdminPrivateChannelCB(id=ch["id"], action="toggle").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="👥 Подписчики",
        callback_data=AdminPrivateChannelCB(id=ch["id"], action="subs").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=AdminPrivateChannelCB(id=ch["id"], action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="private_channels").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminPrivateChannelCB.filter(F.action == "toggle"))
async def toggle_channel(
    callback: CallbackQuery, callback_data: AdminPrivateChannelCB, db: aiosqlite.Connection,
):
    ch = await get_channel(db, callback_data.id)
    if not ch:
        await callback.answer("Канал не найден", show_alert=True)
        return
    new_active = 0 if ch["is_active"] else 1
    await update_channel(db, callback_data.id, is_active=new_active)
    # Also toggle the linked product
    if ch["product_id"]:
        await update_product(db, ch["product_id"], is_active=new_active)
    status = "включен" if new_active else "отключен"
    await callback.answer(f"Канал {status}", show_alert=True)

    callback_data_new = AdminPrivateChannelCB(id=callback_data.id, action="view")
    await view_channel(callback, callback_data_new, db)


@router.callback_query(AdminPrivateChannelCB.filter(F.action == "subs"))
async def show_subs(
    callback: CallbackQuery, callback_data: AdminPrivateChannelCB, db: aiosqlite.Connection,
):
    ch = await get_channel(db, callback_data.id)
    if not ch:
        await callback.answer("Канал не найден", show_alert=True)
        return

    subs = await get_channel_subscriptions(db, ch["id"])
    if not subs:
        text = f"👥 Подписчики «{ch['name']}»\n\nНет активных подписок."
    else:
        lines = [f"👥 Подписчики «{ch['name']}» ({len(subs)}):\n"]
        for s in subs:
            username = f"@{s['username']}" if s["username"] else str(s["user_id"])
            lines.append(f"  {username} — до {s['expires_at'][:16]}")
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPrivateChannelCB(id=callback_data.id, action="view").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminPrivateChannelCB.filter(F.action == "delete"))
async def confirm_delete(
    callback: CallbackQuery, callback_data: AdminPrivateChannelCB, db: aiosqlite.Connection,
):
    ch = await get_channel(db, callback_data.id)
    if ch and ch["product_id"]:
        await delete_product(db, ch["product_id"])
    await delete_channel(db, callback_data.id)
    await callback.answer("Приватка удалена (товар тоже)", show_alert=True)
    await show_channels(callback, db, None)


# --- Creation flow ---

@router.callback_query(AdminPrivateChannelCB.filter(F.action == "add"))
async def start_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminPrivChStates.waiting_name)
    await callback.message.edit_text("🔐 Введите название приватки:")
    await callback.answer()


@router.message(AdminPrivChStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(ch_name=message.text.strip())
    await state.set_state(AdminPrivChStates.waiting_channel_id)
    await message.answer(
        "Введите Telegram Channel ID (числовой, например -1001234567890):\n\n"
        "Бот должен быть админом этого канала!"
    )


@router.message(AdminPrivChStates.waiting_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("Введите числовой ID канала:")
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminPrivChStates.waiting_price)
    await message.answer("Введите цену подписки (в рублях):")


@router.message(AdminPrivChStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Введите корректную цену:")
        return
    await state.update_data(price=price)
    await state.set_state(AdminPrivChStates.waiting_duration)
    await message.answer("Введите срок подписки в днях:")


@router.message(AdminPrivChStates.waiting_duration)
async def process_duration(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Введите корректное количество дней:")
        return
    await state.update_data(duration_days=days)
    await state.set_state(AdminPrivChStates.waiting_description)
    await message.answer("Введите описание (или '-' для пропуска):")


@router.message(AdminPrivChStates.waiting_description)
async def process_description(message: Message, db: aiosqlite.Connection, state: FSMContext):
    desc = message.text.strip() if message.text.strip() != "-" else ""
    await state.update_data(description=desc)

    # Show category selection
    categories = await get_all_root_categories(db)
    if not categories:
        await message.answer("Сначала создайте хотя бы одну категорию в разделе Категории!")
        await state.clear()
        return

    kb = InlineKeyboardBuilder()
    for cat in categories:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{cat['name']}",
            callback_data=f"apch_cat:{cat['id']}",
        ))
        # Show subcategories
        subcats = await get_all_subcategories(db, cat["id"])
        for sub in subcats:
            sub_emoji = sub["emoji"] + " " if sub["emoji"] else ""
            kb.row(InlineKeyboardButton(
                text=f"  └ {sub_emoji}{sub['name']}",
                callback_data=f"apch_cat:{sub['id']}",
            ))

    await state.set_state(AdminPrivChStates.waiting_category)
    await message.answer("Выберите категорию для товара приватки:", reply_markup=kb.as_markup())


@router.callback_query(AdminPrivChStates.waiting_category, F.data.startswith("apch_cat:"))
async def process_category(
    callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext,
):
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()

    # 1. Create the product (infinite) in the chosen category
    product_id = await create_product(
        db,
        category_id=cat_id,
        name=data["ch_name"],
        description=data.get("description", "") or f"Подписка на приватный канал на {data['duration_days']} дней",
        price=data["price"],
    )
    # Make infinite
    await update_product(db, product_id, is_infinite=1)

    # 2. Create the private channel record linked to the product
    channel_pk = await create_channel(
        db,
        name=data["ch_name"],
        channel_id=data["channel_id"],
        price=data["price"],
        duration_days=data["duration_days"],
        created_by=callback.from_user.id,
        description=data.get("description", ""),
        product_id=product_id,
    )

    await state.clear()

    text = (
        f"✅ Приватка «{data['ch_name']}» создана!\n\n"
        f"📦 Товар создан в магазине (ID: {product_id})\n"
        f"💰 Цена: {format_price(data['price'])}\n"
        f"📅 Срок: {data['duration_days']} дней\n\n"
        f"Убедитесь, что бот является админом канала."
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ К приваткам",
        callback_data=AdminPanelCB(section="private_channels").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
