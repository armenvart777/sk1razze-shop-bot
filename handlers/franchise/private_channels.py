from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchisePrivateChannelCB, FranchisePanelCB
from db.queries.private_channels import (
    get_franchise_channels, get_channel, create_channel,
    update_channel, delete_channel, get_channel_subscriptions,
)
from db.queries.products import create_franchise_product, update_product, delete_product
from db.queries.categories import get_all_root_categories, get_all_subcategories
from utils.formatting import format_price

router = Router(name="franchise_private_channels")


class FranchisePrivChStates(StatesGroup):
    waiting_name = State()
    waiting_channel_id = State()
    waiting_price = State()
    waiting_duration = State()
    waiting_description = State()
    waiting_category = State()


@router.callback_query(FranchisePanelCB.filter(F.action == "private_channels"), IsFranchiseOwner())
async def show_channels(
    callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict, state: FSMContext,
):
    await state.clear()
    channels = await get_franchise_channels(db, franchise["id"])

    kb = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch["is_active"] else "❌"
        kb.row(InlineKeyboardButton(
            text=f"{status} {ch['name']} — {format_price(ch['price'])} / {ch['duration_days']}д",
            callback_data=FranchisePrivateChannelCB(id=ch["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="➕ Добавить приватку",
        callback_data=FranchisePrivateChannelCB(id=0, action="add").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))

    try:
        await callback.message.edit_text(
            "🔐 Ваши приватки:", reply_markup=kb.as_markup(),
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "🔐 Ваши приватки:", reply_markup=kb.as_markup(),
        )
    await callback.answer()


@router.callback_query(FranchisePrivateChannelCB.filter(F.action == "view"), IsFranchiseOwner())
async def view_channel(
    callback: CallbackQuery, callback_data: FranchisePrivateChannelCB,
    db: aiosqlite.Connection, franchise: dict,
):
    ch = await get_channel(db, callback_data.id)
    if not ch or ch["franchise_id"] != franchise["id"]:
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
        f"👥 Активных подписок: {len(subs)}"
    )
    if ch["product_id"]:
        text += f"\n📦 Товар ID: {ch['product_id']}"

    kb = InlineKeyboardBuilder()
    toggle_text = "⏸ Отключить" if ch["is_active"] else "▶️ Включить"
    kb.row(InlineKeyboardButton(
        text=toggle_text,
        callback_data=FranchisePrivateChannelCB(id=ch["id"], action="toggle").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="👥 Подписчики",
        callback_data=FranchisePrivateChannelCB(id=ch["id"], action="subs").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=FranchisePrivateChannelCB(id=ch["id"], action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="private_channels").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(FranchisePrivateChannelCB.filter(F.action == "toggle"), IsFranchiseOwner())
async def toggle_channel(
    callback: CallbackQuery, callback_data: FranchisePrivateChannelCB,
    db: aiosqlite.Connection, franchise: dict,
):
    ch = await get_channel(db, callback_data.id)
    if not ch or ch["franchise_id"] != franchise["id"]:
        await callback.answer("Канал не найден", show_alert=True)
        return
    new_active = 0 if ch["is_active"] else 1
    await update_channel(db, callback_data.id, is_active=new_active)
    if ch["product_id"]:
        await update_product(db, ch["product_id"], is_active=new_active)
    status = "включен" if new_active else "отключен"
    await callback.answer(f"Канал {status}", show_alert=True)

    callback_data_new = FranchisePrivateChannelCB(id=callback_data.id, action="view")
    await view_channel(callback, callback_data_new, db, franchise)


@router.callback_query(FranchisePrivateChannelCB.filter(F.action == "subs"), IsFranchiseOwner())
async def show_subs(
    callback: CallbackQuery, callback_data: FranchisePrivateChannelCB,
    db: aiosqlite.Connection, franchise: dict,
):
    ch = await get_channel(db, callback_data.id)
    if not ch or ch["franchise_id"] != franchise["id"]:
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
        callback_data=FranchisePrivateChannelCB(id=callback_data.id, action="view").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(FranchisePrivateChannelCB.filter(F.action == "delete"), IsFranchiseOwner())
async def do_delete(
    callback: CallbackQuery, callback_data: FranchisePrivateChannelCB,
    db: aiosqlite.Connection, franchise: dict, state: FSMContext,
):
    ch = await get_channel(db, callback_data.id)
    if not ch or ch["franchise_id"] != franchise["id"]:
        await callback.answer("Канал не найден", show_alert=True)
        return
    if ch["product_id"]:
        await delete_product(db, ch["product_id"])
    await delete_channel(db, callback_data.id)
    await callback.answer("Приватка удалена", show_alert=True)
    await show_channels(callback, db, franchise, state)


# --- Creation flow ---

@router.callback_query(FranchisePrivateChannelCB.filter(F.action == "add"), IsFranchiseOwner())
async def start_add(callback: CallbackQuery, state: FSMContext, franchise: dict):
    await state.set_state(FranchisePrivChStates.waiting_name)
    await state.update_data(franchise_id=franchise["id"])
    await callback.message.edit_text("🔐 Введите название приватки:")
    await callback.answer()


@router.message(FranchisePrivChStates.waiting_name, IsFranchiseOwner())
async def process_name(message: Message, state: FSMContext):
    await state.update_data(ch_name=message.text.strip())
    await state.set_state(FranchisePrivChStates.waiting_channel_id)
    await message.answer(
        "Введите Telegram Channel ID (числовой, например -1001234567890):\n\n"
        "Бот должен быть админом этого канала!"
    )


@router.message(FranchisePrivChStates.waiting_channel_id, IsFranchiseOwner())
async def process_channel_id(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("Введите числовой ID канала:")
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(FranchisePrivChStates.waiting_price)
    await message.answer("Введите цену подписки (в рублях):")


@router.message(FranchisePrivChStates.waiting_price, IsFranchiseOwner())
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Введите корректную цену:")
        return
    await state.update_data(price=price)
    await state.set_state(FranchisePrivChStates.waiting_duration)
    await message.answer("Введите срок подписки в днях:")


@router.message(FranchisePrivChStates.waiting_duration, IsFranchiseOwner())
async def process_duration(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Введите корректное количество дней:")
        return
    await state.update_data(duration_days=days)
    await state.set_state(FranchisePrivChStates.waiting_description)
    await message.answer("Введите описание (или '-' для пропуска):")


@router.message(FranchisePrivChStates.waiting_description, IsFranchiseOwner())
async def process_description(message: Message, db: aiosqlite.Connection, state: FSMContext):
    desc = message.text.strip() if message.text.strip() != "-" else ""
    await state.update_data(description=desc)

    # Show category selection
    categories = await get_all_root_categories(db)
    if not categories:
        await message.answer("Сначала создайте хотя бы одну категорию!")
        await state.clear()
        return

    kb = InlineKeyboardBuilder()
    for cat in categories:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{cat['name']}",
            callback_data=f"fpch_cat:{cat['id']}",
        ))
        subcats = await get_all_subcategories(db, cat["id"])
        for sub in subcats:
            sub_emoji = sub["emoji"] + " " if sub["emoji"] else ""
            kb.row(InlineKeyboardButton(
                text=f"  └ {sub_emoji}{sub['name']}",
                callback_data=f"fpch_cat:{sub['id']}",
            ))

    await state.set_state(FranchisePrivChStates.waiting_category)
    await message.answer("Выберите категорию для товара приватки:", reply_markup=kb.as_markup())


@router.callback_query(FranchisePrivChStates.waiting_category, F.data.startswith("fpch_cat:"), IsFranchiseOwner())
async def process_category(
    callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext,
):
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    franchise_id = data["franchise_id"]

    # 1. Create franchise product (infinite)
    product_id = await create_franchise_product(
        db,
        franchise_id=franchise_id,
        category_id=cat_id,
        name=data["ch_name"],
        description=data.get("description", "") or f"Подписка на приватный канал на {data['duration_days']} дней",
        price=data["price"],
    )
    await update_product(db, product_id, is_infinite=1)

    # 2. Create private channel linked to the product
    await create_channel(
        db,
        name=data["ch_name"],
        channel_id=data["channel_id"],
        price=data["price"],
        duration_days=data["duration_days"],
        created_by=callback.from_user.id,
        description=data.get("description", ""),
        franchise_id=franchise_id,
        product_id=product_id,
    )

    await state.clear()

    text = (
        f"✅ Приватка «{data['ch_name']}» создана!\n\n"
        f"📦 Товар добавлен в магазин (ID: {product_id})\n"
        f"💰 Цена: {format_price(data['price'])}\n"
        f"📅 Срок: {data['duration_days']} дней\n\n"
        f"Убедитесь, что бот является админом канала."
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ К приваткам",
        callback_data=FranchisePanelCB(action="private_channels").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
