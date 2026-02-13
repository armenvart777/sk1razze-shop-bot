from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminFranchiseCB, AdminConfirmCB
from keyboards.inline import (
    admin_franchises_keyboard, admin_franchise_detail_keyboard,
    admin_confirm_keyboard, admin_back_keyboard,
)
from db.queries.franchises import (
    get_all_franchises, get_franchise, create_franchise,
    update_franchise, delete_franchise, get_franchise_stats,
)
from db.queries.users import get_user, search_user
from states.admin_states import AdminFranchiseStates
from utils.formatting import format_price
from services.bot_manager import start_franchise_bot, stop_franchise_bot

router = Router(name="admin_franchises")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# === List all franchises ===

@router.callback_query(AdminPanelCB.filter(F.section == "franchises"))
async def show_franchises(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    franchises = await get_all_franchises(db)
    kb = admin_franchises_keyboard(franchises)
    try:
        await callback.message.edit_text("🏪 Управление франшизами:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("🏪 Управление франшизами:", reply_markup=kb)
    await callback.answer()


# === View franchise detail ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "view"))
async def view_franchise(callback: CallbackQuery, callback_data: AdminFranchiseCB, db: aiosqlite.Connection):
    franchise = await get_franchise(db, callback_data.id)
    if not franchise:
        await callback.answer("Франшиза не найдена", show_alert=True)
        return

    status = "✅ Активна" if franchise["is_active"] else "❌ Неактивна"
    owner = await get_user(db, franchise["owner_id"])
    owner_label = f"@{owner['username']}" if owner and owner["username"] else str(franchise["owner_id"])

    text = (
        f"🏪 {franchise['name']}\n\n"
        f"🆔 ID: {franchise['id']}\n"
        f"👤 Владелец: {owner_label} (ID: {franchise['owner_id']})\n"
        f"🤖 Бот: @{franchise['bot_username'] or '—'}\n"
        f"📊 Статус: {status}\n"
        f"💰 Комиссия владельца: {franchise['commission_owner_product']}%\n"
        f"💰 Комиссия франчайзи: {franchise['commission_own_product']}%\n"
        f"📅 Создана: {franchise['created_at'][:16]}"
    )
    kb = admin_franchise_detail_keyboard(franchise["id"], is_active=franchise["is_active"])
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# === Create franchise — Step 1: user ID ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "create"))
async def start_create_franchise(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminFranchiseStates.waiting_user_id)
    await callback.message.edit_text(
        "Введите Telegram ID или @username будущего франчайзи:"
    )
    await callback.answer()


@router.message(AdminFranchiseStates.waiting_user_id)
async def process_user_id(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        return

    query = message.text.strip()
    user = await search_user(db, query)

    if not user:
        # Try to parse as raw integer ID even if user not in DB yet
        if query.lstrip("@").isdigit():
            owner_id = int(query)
        else:
            await message.answer(
                "❌ Пользователь не найден в базе.\n"
                "Введите корректный Telegram ID или @username:"
            )
            return
    else:
        owner_id = user["id"]

    await state.update_data(owner_id=owner_id)
    await state.set_state(AdminFranchiseStates.waiting_bot_token)
    await message.answer(
        f"👤 Владелец: {owner_id}\n\n"
        "Теперь введите Bot Token для франшизы (получите у @BotFather):"
    )


# === Create franchise — Step 2: bot token ===

@router.message(AdminFranchiseStates.waiting_bot_token)
async def process_bot_token(message: Message, state: FSMContext):
    if not message.text:
        return

    token = message.text.strip()

    # Validate token by calling Telegram API
    try:
        test_bot = Bot(token=token)
        info = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer(
            "❌ Невалидный токен бота. Проверьте и введите заново:"
        )
        return

    bot_username = info.username
    await state.update_data(bot_token=token, bot_username=bot_username)
    await state.set_state(AdminFranchiseStates.waiting_name)
    await message.answer(
        f"✅ Бот валиден: @{bot_username}\n\n"
        "Введите название франшизы:"
    )


# === Create franchise — Step 3: name ===

@router.message(AdminFranchiseStates.waiting_name)
async def process_franchise_name(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        return

    name = message.text.strip()
    data = await state.get_data()

    franchise_id = await create_franchise(
        db,
        owner_id=data["owner_id"],
        bot_token=data["bot_token"],
        bot_username=data.get("bot_username"),
        name=name,
    )

    await state.clear()

    # Автозапуск бота
    started = await start_franchise_bot(data["bot_token"])
    status_msg = "✅ Бот запущен автоматически" if started else "⚠️ Не удалось запустить бота"

    await message.answer(
        f"✅ Франшиза '{name}' создана (ID: {franchise_id})\n\n"
        f"🤖 Бот: @{data.get('bot_username', '—')}\n"
        f"👤 Владелец: {data['owner_id']}\n\n"
        f"{status_msg}",
        reply_markup=admin_back_keyboard("franchises"),
    )


# === Toggle is_active ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "toggle"))
async def toggle_franchise(callback: CallbackQuery, callback_data: AdminFranchiseCB, db: aiosqlite.Connection):
    franchise = await get_franchise(db, callback_data.id)
    if not franchise:
        await callback.answer("Франшиза не найдена", show_alert=True)
        return

    new_active = 0 if franchise["is_active"] else 1
    await update_franchise(db, callback_data.id, is_active=new_active)

    # Динамически запускаем/останавливаем бота
    if new_active:
        await start_franchise_bot(franchise["bot_token"])
        status = "активирована ✅ Бот запущен"
    else:
        await stop_franchise_bot(franchise["bot_token"])
        status = "деактивирована ❌ Бот остановлен"

    await callback.answer(f"Франшиза {status}", show_alert=True)

    # Refresh detail view
    franchise = await get_franchise(db, callback_data.id)
    status_text = "✅ Активна" if franchise["is_active"] else "❌ Неактивна"
    owner = await get_user(db, franchise["owner_id"])
    owner_label = f"@{owner['username']}" if owner and owner["username"] else str(franchise["owner_id"])

    note = ""

    text = (
        f"🏪 {franchise['name']}\n\n"
        f"🆔 ID: {franchise['id']}\n"
        f"👤 Владелец: {owner_label} (ID: {franchise['owner_id']})\n"
        f"🤖 Бот: @{franchise['bot_username'] or '—'}\n"
        f"📊 Статус: {status_text}\n"
        f"💰 Комиссия владельца: {franchise['commission_owner_product']}%\n"
        f"💰 Комиссия франчайзи: {franchise['commission_own_product']}%\n"
        f"📅 Создана: {franchise['created_at'][:16]}"
        f"{note}"
    )
    kb = admin_franchise_detail_keyboard(franchise["id"], is_active=franchise["is_active"])
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)


# === Commission rates ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "rates"))
async def show_rates(callback: CallbackQuery, callback_data: AdminFranchiseCB, db: aiosqlite.Connection):
    franchise = await get_franchise(db, callback_data.id)
    if not franchise:
        await callback.answer("Франшиза не найдена", show_alert=True)
        return

    text = (
        f"💰 Комиссии франшизы «{franchise['name']}»\n\n"
        f"📌 Комиссия владельца (owner): {franchise['commission_owner_product']}%\n"
        f"📌 Комиссия франчайзи (own): {franchise['commission_own_product']}%\n\n"
        "Выберите ставку для редактирования:"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text=f"Owner Rate ({franchise['commission_owner_product']}%)",
        callback_data=f"fran_rate:{callback_data.id}:owner",
    ))
    kb.row(InlineKeyboardButton(
        text=f"Own Rate ({franchise['commission_own_product']}%)",
        callback_data=f"fran_rate:{callback_data.id}:own",
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminFranchiseCB(id=callback_data.id, action="view").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("fran_rate:"))
async def start_edit_rate(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    franchise_id = int(parts[1])
    rate_type = parts[2]  # "owner" or "own"

    await state.set_state(AdminFranchiseStates.editing_rate)
    await state.update_data(franchise_id=franchise_id, rate_type=rate_type)

    label = "владельца (owner)" if rate_type == "owner" else "франчайзи (own)"
    await callback.message.edit_text(
        f"Введите новую ставку комиссии {label} (число, например 5.0):"
    )
    await callback.answer()


@router.message(AdminFranchiseStates.editing_rate)
async def process_rate_value(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        return

    try:
        value = float(message.text.strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (>= 0):")
        return

    data = await state.get_data()
    franchise_id = data["franchise_id"]
    rate_type = data["rate_type"]

    if rate_type == "owner":
        await update_franchise(db, franchise_id, commission_owner_product=value)
    else:
        await update_franchise(db, franchise_id, commission_own_product=value)

    await state.clear()

    label = "владельца" if rate_type == "owner" else "франчайзи"
    await message.answer(
        f"✅ Ставка комиссии {label} обновлена: {value}%",
        reply_markup=admin_back_keyboard("franchises"),
    )


# === Franchise stats ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "stats"))
async def show_franchise_stats(callback: CallbackQuery, callback_data: AdminFranchiseCB, db: aiosqlite.Connection):
    franchise = await get_franchise(db, callback_data.id)
    if not franchise:
        await callback.answer("Франшиза не найдена", show_alert=True)
        return

    stats = await get_franchise_stats(db, callback_data.id)

    text = (
        f"📊 Статистика франшизы «{franchise['name']}»\n\n"
        f"📦 Заказов: {stats['order_count']}\n"
        f"💵 Сумма продаж: {format_price(stats['total_sales'])}\n"
        f"💰 Заработок франчайзи: {format_price(stats['total_earned'])}\n"
        f"💰 Заработок владельца: {format_price(stats['owner_earned'])}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminFranchiseCB(id=callback_data.id, action="view").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# === Delete franchise ===

@router.callback_query(AdminFranchiseCB.filter(F.action == "delete"))
async def confirm_delete_franchise(callback: CallbackQuery, callback_data: AdminFranchiseCB):
    kb = admin_confirm_keyboard("del_fran", callback_data.id)
    await callback.message.edit_text("⚠️ Удалить эту франшизу? Все данные будут потеряны.", reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminConfirmCB.filter((F.target == "del_fran") & (F.action == "yes")))
async def do_delete_franchise(callback: CallbackQuery, callback_data: AdminConfirmCB, db: aiosqlite.Connection):
    await delete_franchise(db, callback_data.target_id)
    await callback.answer("✅ Франшиза удалена", show_alert=True)
    await callback.message.edit_text("✅ Франшиза удалена.", reply_markup=admin_back_keyboard("franchises"))


@router.callback_query(AdminConfirmCB.filter((F.target == "del_fran") & (F.action == "no")))
async def cancel_delete_franchise(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено.", reply_markup=admin_back_keyboard("franchises"))
    await callback.answer()
