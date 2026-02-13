from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB
from keyboards.inline import admin_back_keyboard
from db.queries.users import get_user_count, get_users_page, search_user, toggle_ban, set_balance
from states.admin_states import AdminUserSearchStates, AdminBalanceAdjustStates
from utils.formatting import format_price

router = Router(name="admin_users")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "users"))
async def show_users_menu(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    total = await get_user_count(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔍 Поиск по ID/username", callback_data="admin_user_search"))
    kb.row(InlineKeyboardButton(text="📋 Последние пользователи", callback_data="admin_users_list:0"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text(f"👥 Пользователи ({total} всего):", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminUserSearchStates.waiting_query)
    await callback.message.edit_text("Введите Telegram ID или @username пользователя:")
    await callback.answer()


@router.message(AdminUserSearchStates.waiting_query)
async def process_search(message: Message, db: aiosqlite.Connection, state: FSMContext):
    user = await search_user(db, message.text.strip())
    await state.clear()

    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=admin_back_keyboard("users"))
        return

    await _show_user_detail(message, user)


async def _show_user_detail(message: Message, user):
    status = "🚫 Забанен" if user["is_banned"] else "✅ Активен"
    text = (
        f"👤 Пользователь:\n\n"
        f"🆔 ID: {user['id']}\n"
        f"👤 Username: @{user['username'] or '—'}\n"
        f"💰 Баланс: {format_price(user['balance'])}\n"
        f"💸 Пополнено: {format_price(user['total_deposited'])}\n"
        f"👥 Рефералов: {user['referral_count']}\n"
        f"📅 Регистрация: {user['registered_at'][:16]}\n"
        f"📊 Статус: {status}"
    )
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    ban_text = "🔓 Разбанить" if user["is_banned"] else "🚫 Забанить"
    kb.row(InlineKeyboardButton(text=ban_text, callback_data=f"admin_ban:{user['id']}"))
    kb.row(InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_balance:{user['id']}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="users").pack()))
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("admin_ban:"))
async def ban_user(callback: CallbackQuery, db: aiosqlite.Connection):
    user_id = int(callback.data.split(":")[1])
    await toggle_ban(db, user_id)
    await callback.answer("✅ Статус обновлён", show_alert=True)


@router.callback_query(F.data.startswith("admin_balance:"))
async def start_balance_adjust(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.set_state(AdminBalanceAdjustStates.waiting_amount)
    await state.update_data(target_user_id=user_id)
    await callback.message.edit_text("Введите новый баланс (число):")
    await callback.answer()


@router.message(AdminBalanceAdjustStates.waiting_amount)
async def process_balance(message: Message, db: aiosqlite.Connection, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число:")
        return

    data = await state.get_data()
    await set_balance(db, data["target_user_id"], amount)
    await state.clear()
    await message.answer(f"✅ Баланс установлен: {format_price(amount)}")


@router.callback_query(F.data.startswith("admin_users_list:"))
async def list_users(callback: CallbackQuery, db: aiosqlite.Connection):
    page = int(callback.data.split(":")[1])
    users = await get_users_page(db, offset=page * 10)
    total = await get_user_count(db)

    if not users:
        await callback.message.edit_text("Пользователей нет.", reply_markup=admin_back_keyboard("users"))
        await callback.answer()
        return

    text_parts = [f"👥 Пользователи (стр. {page + 1}):\n"]
    for u in users:
        status = "🚫" if u["is_banned"] else "✅"
        text_parts.append(
            f"{status} {u['id']} | @{u['username'] or '—'} | {format_price(u['balance'])}"
        )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_users_list:{page - 1}"))
    total_pages = max(1, (total + 9) // 10)
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_users_list:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="users").pack()))

    await callback.message.edit_text("\n".join(text_parts), reply_markup=kb.as_markup())
    await callback.answer()
