from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchisePanelCB
from keyboards.inline import franchise_panel_keyboard
from db.queries.franchises import get_franchise_stats, get_franchise_commissions
from db.queries.products import get_franchise_products
from db.queries.users import get_user
from db.queries.settings import get_setting
from utils.formatting import format_price
from config import settings

router = Router(name="franchise_panel")


class FranchiseBroadcastStates(StatesGroup):
    waiting_message = State()


# === Helper: build panel text ===

async def _build_panel_text(db: aiosqlite.Connection, franchise: dict) -> str:
    stats = await get_franchise_stats(db, franchise["id"])
    owner = await get_user(db, franchise["owner_id"])
    balance = owner["balance"] if owner else 0.0

    support_url = await get_setting(db, "support_url") or ""
    channel_username = await get_setting(db, "channel_username") or settings.CHANNEL_USERNAME

    ch_display = f"https://t.me/{channel_username.lstrip('@')}" if channel_username else "не задано"

    text = (
        f"🏪 Информация о франшизе:\n\n"
        f"📌 Название: {franchise['name']}\n"
        f"👥 Пользователей: {stats['user_count']}\n"
        f"💰 Заработано: {format_price(stats['total_earned'])}\n"
        f"💵 Баланс: {format_price(balance)}\n\n"
        f"📢 Обязательная подписка: {ch_display}\n"
    )
    if support_url:
        text += f"🆘 Поддержка: {support_url}\n"

    return text


# === /manage — главная панель франчайзи ===

@router.message(Command("manage"), IsFranchiseOwner())
async def cmd_manage(message: Message, db: aiosqlite.Connection, state: FSMContext, franchise: dict):
    await state.clear()
    text = await _build_panel_text(db, franchise)
    await message.answer(text, reply_markup=franchise_panel_keyboard(), disable_web_page_preview=True)


async def show_panel(callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict):
    text = await _build_panel_text(db, franchise)
    try:
        await callback.message.edit_text(text, reply_markup=franchise_panel_keyboard(), disable_web_page_preview=True)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=franchise_panel_keyboard(), disable_web_page_preview=True)
    await callback.answer()


# === Кнопка «Назад» → та же панель ===

@router.callback_query(FranchisePanelCB.filter(F.action == "back"), IsFranchiseOwner())
async def panel_back(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext, franchise: dict):
    await state.clear()
    text = await _build_panel_text(db, franchise)
    try:
        await callback.message.edit_text(text, reply_markup=franchise_panel_keyboard(), disable_web_page_preview=True)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=franchise_panel_keyboard(), disable_web_page_preview=True)
    await callback.answer()


# === Мои товары ===

@router.callback_query(FranchisePanelCB.filter(F.action == "products"), IsFranchiseOwner())
async def panel_products(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    from keyboards.inline import franchise_products_keyboard

    products = await get_franchise_products(db, franchise["id"])
    text = f"📦 Ваши товары ({len(products)} шт.):"
    kb = franchise_products_keyboard(products)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# === Статистика ===

@router.callback_query(FranchisePanelCB.filter(F.action == "stats"), IsFranchiseOwner())
async def panel_stats(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    stats = await get_franchise_stats(db, franchise["id"])

    text = (
        f"📊 Статистика франшизы «{franchise['name']}»\n\n"
        f"👥 Пользователей: {stats['user_count']}\n"
        f"📋 Всего заказов: {stats['order_count']}\n"
        f"💰 Общая сумма продаж: {format_price(stats['total_sales'])}\n"
        f"💵 Ваш доход (комиссии): {format_price(stats['total_earned'])}\n"
        f"🏦 Доход владельца платформы: {format_price(stats['owner_earned'])}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))
    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# === Рассылка ===

@router.callback_query(FranchisePanelCB.filter(F.action == "broadcast"), IsFranchiseOwner())
async def panel_broadcast_start(callback: CallbackQuery, state: FSMContext, franchise: dict):
    await state.set_state(FranchiseBroadcastStates.waiting_message)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))
    try:
        await callback.message.edit_text(
            f"📢 Рассылка по франшизе «{franchise['name']}»\n\n"
            f"Отправьте сообщение для рассылки (текст, фото и т.д.):\n"
            f"Или нажмите «Отмена».",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            f"📢 Рассылка по франшизе «{franchise['name']}»\n\n"
            f"Отправьте сообщение для рассылки (текст, фото и т.д.):\n"
            f"Или нажмите «Отмена».",
            reply_markup=kb.as_markup(),
        )
    await callback.answer()


@router.message(FranchiseBroadcastStates.waiting_message, IsFranchiseOwner())
async def panel_broadcast_send(message: Message, db: aiosqlite.Connection, state: FSMContext, franchise: dict, bot: Bot):
    await state.clear()

    # Save broadcast to DB for admin moderation
    if message.photo:
        msg_type = "photo"
        photo_file_id = message.photo[-1].file_id
        caption = message.caption or ""
        text_content = None
    elif message.text:
        msg_type = "text"
        photo_file_id = None
        caption = None
        text_content = message.text
    else:
        await message.answer("Отправьте текст или фото.")
        return

    cursor = await db.execute(
        """INSERT INTO franchise_broadcasts (franchise_id, owner_id, message_type, text_content, photo_file_id, caption)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (franchise["id"], message.from_user.id, msg_type, text_content, photo_file_id, caption),
    )
    broadcast_id = cursor.lastrowid
    await db.commit()

    await message.answer(
        "✅ Заявка на рассылку отправлена на модерацию.\n"
        "Ожидайте одобрения администратора."
    )

    # Send to admin for approval via main bot
    from services.bot_manager import get_main_bot
    from keyboards.callbacks import FranchiseBroadcastCB

    main_bot = get_main_bot()
    if not main_bot:
        return

    admin_text = (
        f"📢 Заявка на рассылку от франшизы\n\n"
        f"🏪 Франшиза: {franchise['name']}\n"
        f"🆔 ID заявки: {broadcast_id}\n\n"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=FranchiseBroadcastCB(franchise_id=broadcast_id, action="approve").pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=FranchiseBroadcastCB(franchise_id=broadcast_id, action="reject").pack(),
        ),
    )

    for admin_id in settings.ADMIN_IDS:
        try:
            if msg_type == "photo":
                # Download from franchise bot and re-upload via main bot
                photo_to_send = photo_file_id
                if main_bot.id != bot.id:
                    try:
                        from io import BytesIO
                        from aiogram.types import BufferedInputFile
                        file = await bot.get_file(photo_file_id)
                        bio = BytesIO()
                        await bot.download_file(file.file_path, bio)
                        bio.seek(0)
                        photo_to_send = BufferedInputFile(bio.read(), filename="broadcast.jpg")
                    except Exception:
                        pass
                await main_bot.send_photo(
                    admin_id, photo=photo_to_send,
                    caption=admin_text + (caption or ""),
                    reply_markup=kb.as_markup(), parse_mode=None,
                )
            else:
                await main_bot.send_message(
                    admin_id,
                    admin_text + text_content,
                    reply_markup=kb.as_markup(), parse_mode=None,
                )
        except Exception:
            pass


# === Техническая поддержка ===

@router.callback_query(FranchisePanelCB.filter(F.action == "tech_support"), IsFranchiseOwner())
async def panel_tech_support(callback: CallbackQuery, db: aiosqlite.Connection):
    support_url = await get_setting(db, "support_url") or ""

    kb = InlineKeyboardBuilder()
    if support_url:
        kb.row(InlineKeyboardButton(text="💬 Написать в поддержку", url=support_url))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))

    text = (
        "🔧 Техническая поддержка\n\n"
        "По любым вопросам работы франшизы обращайтесь в поддержку."
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# === Комиссии (постраничный просмотр) ===

@router.callback_query(FranchisePanelCB.filter(F.action == "commissions"), IsFranchiseOwner())
async def panel_commissions(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
    state: FSMContext,
):
    data = await state.get_data()
    page = data.get("comm_page", 0)
    await _show_commissions(callback, db, franchise, page, state)


@router.callback_query(F.data.startswith("fcomm_page:"), IsFranchiseOwner())
async def commissions_page(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
    state: FSMContext,
):
    page = int(callback.data.split(":")[1])
    await _show_commissions(callback, db, franchise, page, state)


async def _show_commissions(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
    page: int,
    state: FSMContext,
):
    per_page = 10
    offset = page * per_page
    commissions = await get_franchise_commissions(db, franchise["id"], offset=offset, limit=per_page + 1)

    has_next = len(commissions) > per_page
    items = commissions[:per_page]

    if not items and page == 0:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=FranchisePanelCB(action="back").pack(),
        ))
        try:
            await callback.message.edit_text(
                "💰 История комиссий пуста.",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                "💰 История комиссий пуста.",
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
        return

    lines = [f"💰 История комиссий (стр. {page + 1}):\n"]
    for c in items:
        date_str = c["order_date"] or c["created_at"] or "—"
        if len(date_str) > 16:
            date_str = date_str[:16]
        product_type = c["product_type"] or "—"
        lines.append(
            f"  📅 {date_str}\n"
            f"  🏷 Тип: {product_type} | Продажа: {format_price(c['sale_amount'])}\n"
            f"  📊 Ставка: {c['commission_rate']}% → {format_price(c['commission_amount'])}\n"
        )

    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"fcomm_page:{page - 1}",
        ))
    if has_next:
        nav.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"fcomm_page:{page + 1}",
        ))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(
        text="◀️ В панель",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))

    await state.update_data(comm_page=page)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
