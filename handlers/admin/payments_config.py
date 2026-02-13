from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB
from db.queries.settings import get_setting, set_setting

router = Router(name="admin_payments_config")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class PaymentSettingsStates(StatesGroup):
    editing_sbp_details = State()
    editing_stars_rate = State()
    editing_setting = State()


def _mask(value: str) -> str:
    """Mask a token/key for display (show first 6 and last 4 chars)."""
    if not value:
        return "не задано"
    if len(value) <= 12:
        return value[:3] + "***"
    return value[:6] + "..." + value[-4:]


@router.callback_query(AdminPanelCB.filter(F.section == "payments"))
async def show_payment_settings(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    crypto_enabled = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
    lolz_enabled = (await get_setting(db, "payment_lolz_enabled")) == "1"
    sbp_enabled = (await get_setting(db, "payment_sbp_enabled")) == "1"
    stars_enabled = (await get_setting(db, "payment_stars_enabled")) == "1"
    min_topup = await get_setting(db, "min_topup_amount") or "50"
    ref_bonus = await get_setting(db, "referral_bonus_percent") or "5"
    sbp_details = await get_setting(db, "sbp_details") or "Не задано"
    stars_rate = await get_setting(db, "stars_rate") or "1.5"

    crypto_status = "✅ Включён" if crypto_enabled else "❌ Выключен"
    lolz_status = "✅ Включён" if lolz_enabled else "❌ Выключен"
    sbp_status = "✅ Включён" if sbp_enabled else "❌ Выключен"
    stars_status = "✅ Включён" if stars_enabled else "❌ Выключен"

    text = (
        f"💳 Настройки оплаты:\n\n"
        f"🔑 CryptoBot: {crypto_status}\n"
        f"💚 Lolz: {lolz_status}\n"
        f"🏦 СБП: {sbp_status}\n"
        f"⭐ Stars: {stars_status}\n\n"
        f"💰 Мин. сумма: {min_topup}₽\n"
        f"👥 Реф. бонус: {ref_bonus}%\n"
        f"⭐ Курс Stars: 1 Star = {stars_rate}₽\n\n"
        f"📋 Реквизиты СБП:\n{sbp_details}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=f"CryptoBot: {'🟢' if crypto_enabled else '🔴'}", callback_data="toggle_crypto"),
        InlineKeyboardButton(text=f"Lolz: {'🟢' if lolz_enabled else '🔴'}", callback_data="toggle_lolz"),
    )
    kb.row(
        InlineKeyboardButton(text=f"СБП: {'🟢' if sbp_enabled else '🔴'}", callback_data="toggle_sbp"),
        InlineKeyboardButton(text=f"Stars: {'🟢' if stars_enabled else '🔴'}", callback_data="toggle_stars"),
    )
    kb.row(InlineKeyboardButton(text="📋 Изменить реквизиты СБП", callback_data="edit_sbp_details"))
    kb.row(InlineKeyboardButton(text="⭐ Изменить курс Stars", callback_data="edit_stars_rate"))
    kb.row(InlineKeyboardButton(text="🔧 Токены и ссылки", callback_data="admin_tokens_menu"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# ==================== Tokens & URLs menu ====================

EDITABLE_SETTINGS = {
    "crypto_bot_token": {"name": "🔑 CryptoBot Token", "masked": True},
    "lolz_token": {"name": "💚 LOLZ Token", "masked": True},
    "lolz_profile": {"name": "💚 LOLZ Profile URL", "masked": False},
    "channel_username": {"name": "📢 Username канала", "masked": False},
    "offer_url": {"name": "📄 Ссылка на оферту", "masked": False},
    "support_url": {"name": "💎 Ссылка на поддержку", "masked": False},
    "reviews_url": {"name": "⭐ Ссылка на отзывы", "masked": False},
    "min_topup_amount": {"name": "💰 Мин. сумма пополнения", "masked": False},
    "referral_bonus_percent": {"name": "👥 Реф. бонус %", "masked": False},
}


@router.callback_query(F.data == "admin_tokens_menu")
async def show_tokens_menu(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    lines = ["🔧 Токены и ссылки:\n"]
    for key, info in EDITABLE_SETTINGS.items():
        val = await get_setting(db, key) or ""
        display = _mask(val) if info["masked"] else (val or "не задано")
        lines.append(f"{info['name']}: {display}")

    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    for key, info in EDITABLE_SETTINGS.items():
        kb.row(InlineKeyboardButton(
            text=f"✏️ {info['name']}",
            callback_data=f"edit_setting:{key}",
        ))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="payments").pack()))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_setting:"))
async def start_edit_setting(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    info = EDITABLE_SETTINGS.get(key)
    if not info:
        await callback.answer("Настройка не найдена", show_alert=True)
        return

    current = await get_setting(db, key) or ""
    display = _mask(current) if info["masked"] else (current or "не задано")

    await state.set_state(PaymentSettingsStates.editing_setting)
    await state.update_data(setting_key=key)

    text = (
        f"✏️ Редактирование: {info['name']}\n\n"
        f"Текущее значение: {display}\n\n"
        f"Введите новое значение (или 'отмена'):"
    )
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text)
    await callback.answer()


@router.message(PaymentSettingsStates.editing_setting)
async def save_setting(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    if not message.text:
        await message.answer("Введите значение текстом:")
        return

    data = await state.get_data()
    key = data["setting_key"]
    value = message.text.strip()

    await set_setting(db, key, value)
    await state.clear()

    info = EDITABLE_SETTINGS.get(key, {})
    name = info.get("name", key)
    await message.answer(f"✅ {name} обновлено!")


# ==================== Payment toggles ====================

@router.callback_query(F.data == "toggle_crypto")
async def toggle_crypto(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    current = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
    await set_setting(db, "payment_crypto_bot_enabled", "0" if current else "1")
    await callback.answer("✅ Обновлено", show_alert=True)
    await show_payment_settings(callback, db, state)


@router.callback_query(F.data == "toggle_lolz")
async def toggle_lolz(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    current = (await get_setting(db, "payment_lolz_enabled")) == "1"
    await set_setting(db, "payment_lolz_enabled", "0" if current else "1")
    await callback.answer("✅ Обновлено", show_alert=True)
    await show_payment_settings(callback, db, state)


@router.callback_query(F.data == "toggle_sbp")
async def toggle_sbp(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    current = (await get_setting(db, "payment_sbp_enabled")) == "1"
    await set_setting(db, "payment_sbp_enabled", "0" if current else "1")
    await callback.answer("✅ Обновлено", show_alert=True)
    await show_payment_settings(callback, db, state)


@router.callback_query(F.data == "toggle_stars")
async def toggle_stars(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    current = (await get_setting(db, "payment_stars_enabled")) == "1"
    await set_setting(db, "payment_stars_enabled", "0" if current else "1")
    await callback.answer("✅ Обновлено", show_alert=True)
    await show_payment_settings(callback, db, state)


# ==================== SBP details & Stars rate ====================

@router.callback_query(F.data == "edit_sbp_details")
async def start_edit_sbp(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PaymentSettingsStates.editing_sbp_details)
    await callback.message.edit_text(
        "📋 Введите новые реквизиты СБП:\n"
        "(номер карты, номер телефона, банк и т.д.)"
    )
    await callback.answer()


@router.message(PaymentSettingsStates.editing_sbp_details)
async def save_sbp_details(message: Message, db: aiosqlite.Connection, state: FSMContext):
    await set_setting(db, "sbp_details", message.text.strip())
    await state.clear()
    await message.answer("✅ Реквизиты СБП обновлены!")


@router.callback_query(F.data == "edit_stars_rate")
async def start_edit_stars_rate(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PaymentSettingsStates.editing_stars_rate)
    await callback.message.edit_text(
        "⭐ Введите курс Stars (сколько рублей за 1 Star):\n"
        "Например: 1.5"
    )
    await callback.answer()


@router.message(PaymentSettingsStates.editing_stars_rate)
async def save_stars_rate(message: Message, db: aiosqlite.Connection, state: FSMContext):
    try:
        rate = float(message.text.strip())
        if rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное положительное число:")
        return

    await set_setting(db, "stars_rate", str(rate))
    await state.clear()
    await message.answer(f"✅ Курс Stars обновлён: 1 Star = {rate}₽")
