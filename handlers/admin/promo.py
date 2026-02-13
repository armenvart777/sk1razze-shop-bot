from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminPromoCB, AdminConfirmCB
from keyboards.inline import admin_confirm_keyboard, admin_back_keyboard
from db.queries.promo import get_all_promos, get_promo, create_promo, delete_promo, toggle_promo
from states.admin_states import AdminPromoStates
from utils.formatting import format_price

router = Router(name="admin_promo")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "promos"))
async def show_promos(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    promos = await get_all_promos(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    for p in promos:
        status = "✅" if p["is_active"] else "❌"
        type_label = format_price(p["discount_value"]) if p["discount_type"] == "fixed" else f"{p['discount_value']}%"
        kb.row(InlineKeyboardButton(
            text=f"{status} {p['code']} | {type_label} | {p['current_uses']}/{p['max_uses']}",
            callback_data=AdminPromoCB(id=p["id"], action="view").pack(),
        ))

    kb.row(InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text("🎟 Управление промокодами:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminPromoCB.filter(F.action == "view"))
async def view_promo(callback: CallbackQuery, callback_data: AdminPromoCB, db: aiosqlite.Connection):
    promo = await get_promo(db, callback_data.id)
    if not promo:
        await callback.answer("Промокод не найден", show_alert=True)
        return

    type_label = "Фиксированная" if promo["discount_type"] == "fixed" else "Процент"
    value_label = format_price(promo["discount_value"]) if promo["discount_type"] == "fixed" else f"{promo['discount_value']}%"
    status = "✅ Активен" if promo["is_active"] else "❌ Неактивен"

    text = (
        f"🎟 Промокод: {promo['code']}\n\n"
        f"📊 Тип: {type_label}\n"
        f"💰 Скидка: {value_label}\n"
        f"🔢 Использований: {promo['current_uses']}/{promo['max_uses']}\n"
        f"📊 Статус: {status}\n"
        f"📅 Создан: {promo['created_at'][:16]}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=AdminPromoCB(id=promo["id"], action="toggle").pack()),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=AdminPromoCB(id=promo["id"], action="delete").pack()),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="promos").pack()))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminPromoCB.filter(F.action == "toggle"))
async def toggle_promo_handler(callback: CallbackQuery, callback_data: AdminPromoCB, db: aiosqlite.Connection):
    await toggle_promo(db, callback_data.id)
    await callback.answer("✅ Статус обновлён", show_alert=True)


@router.callback_query(AdminPromoCB.filter(F.action == "delete"))
async def delete_promo_handler(callback: CallbackQuery, callback_data: AdminPromoCB, db: aiosqlite.Connection):
    await delete_promo(db, callback_data.id)
    await callback.answer("✅ Промокод удалён", show_alert=True)
    promos = await get_all_promos(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for p in promos:
        status = "✅" if p["is_active"] else "❌"
        type_label = format_price(p["discount_value"]) if p["discount_type"] == "fixed" else f"{p['discount_value']}%"
        kb.row(InlineKeyboardButton(
            text=f"{status} {p['code']} | {type_label} | {p['current_uses']}/{p['max_uses']}",
            callback_data=AdminPromoCB(id=p["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text("🎟 Управление промокодами:", reply_markup=kb.as_markup())


# === Create promo ===
@router.callback_query(F.data == "admin_promo_create")
async def start_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminPromoStates.waiting_code)
    await callback.message.edit_text("Введите код промокода (латиницей):")
    await callback.answer()


@router.message(AdminPromoStates.waiting_code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminPromoStates.waiting_discount_type)

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💰 Фиксированная (руб)", callback_data="promo_type:fixed"),
        InlineKeyboardButton(text="📊 Процент (%)", callback_data="promo_type:percent"),
    )
    await message.answer("Выберите тип скидки:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("promo_type:"), AdminPromoStates.waiting_discount_type)
async def promo_type(callback: CallbackQuery, state: FSMContext):
    dtype = callback.data.split(":")[1]
    await state.update_data(discount_type=dtype)
    await state.set_state(AdminPromoStates.waiting_discount_value)
    label = "рублях" if dtype == "fixed" else "процентах"
    await callback.message.edit_text(f"Введите размер скидки (в {label}):")
    await callback.answer()


@router.message(AdminPromoStates.waiting_discount_value)
async def promo_value(message: Message, state: FSMContext):
    try:
        value = float(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число:")
        return
    await state.update_data(discount_value=value)
    await state.set_state(AdminPromoStates.waiting_max_uses)
    await message.answer("Максимальное количество использований (число):")


@router.message(AdminPromoStates.waiting_max_uses)
async def promo_max_uses(message: Message, db: aiosqlite.Connection, state: FSMContext):
    try:
        max_uses = int(message.text.strip())
        if max_uses <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное целое число:")
        return

    data = await state.get_data()
    promo_id = await create_promo(
        db,
        code=data["code"],
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        max_uses=max_uses,
    )
    await state.clear()
    await message.answer(f"✅ Промокод {data['code']} создан (ID: {promo_id})")
