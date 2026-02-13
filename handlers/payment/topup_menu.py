from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
import aiosqlite

from keyboards.callbacks import PaymentMethodCB, CryptoCurrencyCB, AdminSbpCB
from keyboards.inline import (
    payment_methods_keyboard, crypto_currency_keyboard,
    payment_check_keyboard, sbp_admin_keyboard,
    sbp_paid_keyboard, sbp_cancel_keyboard,
)
from db.queries.settings import get_setting
from db.queries.texts import get_text
from db.queries.payments import (
    create_payment, get_payment, update_payment_status, update_payment_external_id,
)
from db.queries.users import update_balance, get_user
from states.user_states import TopupStates
from services.crypto_bot_api import create_invoice as create_crypto_invoice, get_invoice_status
from services.lolz_api import create_payment_link, check_payment as check_lolz_payment
from utils.formatting import format_price
from config import settings
from services.bot_manager import get_main_bot, get_franchise_bot

router = Router(name="topup")


async def _notify_admins_topup(user_id: int, amount: float, method: str, payment_id: int, db: aiosqlite.Connection):
    """Notify platform admins about a confirmed top-up via main bot."""
    main_bot = get_main_bot()
    if not main_bot:
        return
    user = await get_user(db, user_id)
    username = f"@{user['username']}" if user and user["username"] else str(user_id)
    method_names = {"crypto_bot": "CryptoBot", "lolz": "Lolz", "stars": "Stars", "sbp": "СБП"}
    text = (
        f"💳 Платёж подтверждён!\n\n"
        f"👤 Пользователь: {username} (ID: {user_id})\n"
        f"💰 Сумма: {format_price(amount)}\n"
        f"📋 Метод: {method_names.get(method, method)}\n"
        f"🆔 Платёж #{payment_id}"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await main_bot.send_message(admin_id, text, parse_mode=None)
        except Exception:
            pass


# ==================== Menu ====================

async def show_topup_menu(message: Message, db: aiosqlite.Connection, is_franchise_bot: bool = False):
    lolz_enabled = (await get_setting(db, "payment_lolz_enabled")) == "1"
    crypto_enabled = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
    sbp_enabled = (await get_setting(db, "payment_sbp_enabled")) == "1"
    stars_enabled = (await get_setting(db, "payment_stars_enabled")) == "1"
    kb = payment_methods_keyboard(lolz_enabled, crypto_enabled, sbp_enabled, stars_enabled)
    await message.answer("Выберите способ оплаты:", reply_markup=kb)


async def show_topup_menu_cb(callback: CallbackQuery, db: aiosqlite.Connection, is_franchise_bot: bool = False):
    lolz_enabled = (await get_setting(db, "payment_lolz_enabled")) == "1"
    crypto_enabled = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
    sbp_enabled = (await get_setting(db, "payment_sbp_enabled")) == "1"
    stars_enabled = (await get_setting(db, "payment_stars_enabled")) == "1"
    kb = payment_methods_keyboard(lolz_enabled, crypto_enabled, sbp_enabled, stars_enabled)
    try:
        await callback.message.edit_text("Выберите способ оплаты:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("Выберите способ оплаты:", reply_markup=kb)
    await callback.answer()


@router.callback_query(PaymentMethodCB.filter(F.method == "back"))
async def back_to_topup(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext, is_franchise_bot: bool = False):
    await state.clear()
    lolz_enabled = (await get_setting(db, "payment_lolz_enabled")) == "1"
    crypto_enabled = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
    sbp_enabled = (await get_setting(db, "payment_sbp_enabled")) == "1"
    stars_enabled = (await get_setting(db, "payment_stars_enabled")) == "1"
    kb = payment_methods_keyboard(lolz_enabled, crypto_enabled, sbp_enabled, stars_enabled)
    try:
        await callback.message.edit_text("Выберите способ оплаты:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("Выберите способ оплаты:", reply_markup=kb)
    await callback.answer()


# ==================== Choose method → enter amount ====================

@router.callback_query(PaymentMethodCB.filter(F.method == "sbp"))
async def choose_sbp(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupStates.entering_amount)
    await state.update_data(method="sbp", currency="RUB")
    await callback.message.edit_text("Отправьте сумму пополнения:")
    await callback.answer()


@router.callback_query(PaymentMethodCB.filter(F.method == "lolz"))
async def choose_lolz(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupStates.entering_amount)
    await state.update_data(method="lolz", currency="RUB")
    await callback.message.edit_text("Отправьте сумму пополнения:")
    await callback.answer()


@router.callback_query(PaymentMethodCB.filter(F.method == "stars"))
async def choose_stars(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.set_state(TopupStates.entering_amount)
    await state.update_data(method="stars", currency="XTR")
    stars_rate = await get_setting(db, "stars_rate") or "1.5"
    await callback.message.edit_text(
        f"⭐ Пополнение через Telegram Stars\n\n"
        f"Курс: 1 Star = {stars_rate}₽\n\n"
        f"Введите количество Stars для покупки (целое число):"
    )
    await callback.answer()


@router.callback_query(PaymentMethodCB.filter(F.method == "crypto_bot"))
async def choose_crypto(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupStates.choosing_currency)
    await state.update_data(method="crypto_bot")
    kb = crypto_currency_keyboard()
    await callback.message.edit_text("Выберите криптовалюту:", reply_markup=kb)
    await callback.answer()


@router.callback_query(CryptoCurrencyCB.filter(), TopupStates.choosing_currency)
async def choose_amount_crypto(callback: CallbackQuery, callback_data: CryptoCurrencyCB, state: FSMContext):
    await state.update_data(currency=callback_data.currency)
    await state.set_state(TopupStates.entering_amount)
    await callback.message.edit_text("Отправьте сумму пополнения:")
    await callback.answer()


# ==================== Amount input (shared) ====================

@router.message(TopupStates.entering_amount)
async def process_amount(message: Message, db: aiosqlite.Connection, bot: Bot, state: FSMContext, is_franchise_bot: bool = False, franchise: dict | None = None):
    data = await state.get_data()
    method = data.get("method", "crypto_bot")
    currency = data.get("currency", "RUB")

    # Stars: amount is in whole stars
    if method == "stars":
        try:
            stars_count = int(message.text.strip())
            if stars_count < 1 or stars_count > 10000:
                raise ValueError
        except (ValueError, AttributeError):
            await message.answer("❌ Введите целое число от 1 до 10000.")
            return

        stars_rate = float(await get_setting(db, "stars_rate") or "1.5")
        rub_amount = round(stars_count * stars_rate, 2)

        fid = franchise["id"] if franchise else None
        payment_id = await create_payment(db, message.from_user.id, "stars", rub_amount, "XTR", franchise_id=fid)
        await update_payment_external_id(db, payment_id, str(payment_id))

        # Always send Stars invoice via main bot so Stars go to platform owner
        invoice_bot = get_main_bot() or bot if is_franchise_bot else bot
        try:
            await invoice_bot.send_invoice(
                chat_id=message.chat.id,
                title="Пополнение баланса",
                description=f"Пополнение на {format_price(rub_amount)} ({stars_count} Stars)",
                payload=str(payment_id),
                currency="XTR",
                prices=[LabeledPrice(label="Пополнение", amount=stars_count)],
            )
        except Exception:
            # Main bot can't reach user — fallback message
            await message.answer(
                "❌ Для оплаты Stars напишите /start в основном боте, затем повторите."
            )
            await update_payment_status(db, payment_id, "cancelled")
        await state.clear()
        return

    # All other methods: amount is in RUB
    try:
        amount = float(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("❌ Введите корректную сумму числом.")
        return

    min_amount = float(await get_setting(db, "min_topup_amount") or "10")
    if amount < min_amount or amount > 100000:
        await message.answer(f"❌ Сумма должна быть от {format_price(min_amount)} до 100000₽")
        return

    fid = franchise["id"] if franchise else None
    payment_id = await create_payment(db, message.from_user.id, method, amount, currency, franchise_id=fid)

    if method == "crypto_bot":
        crypto_token = await get_setting(db, "crypto_bot_token") or ""
        invoice = await create_crypto_invoice(
            amount=amount,
            currency=currency,
            description="Пополнение баланса Sk1razze Store",
            payload=str(payment_id),
            token=crypto_token,
        )
        if invoice:
            await update_payment_external_id(db, payment_id, str(invoice["invoice_id"]))
            pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url", "")
            kb = payment_check_keyboard(pay_url, payment_id)
            await message.answer("Для оплаты перейдите по ссылке!", reply_markup=kb)
        else:
            await message.answer("❌ Ошибка создания платежа. Проверьте настройки CryptoBot.")
            await update_payment_status(db, payment_id, "cancelled")

    elif method == "lolz":
        comment = f"sk1razze_{payment_id}"
        lolz_profile = await get_setting(db, "lolz_profile") or ""
        pay_url = await create_payment_link(amount, comment, profile=lolz_profile)
        if pay_url:
            await update_payment_external_id(db, payment_id, comment)
            text = (
                f"Для оплаты перейдите по ссылке!\n"
                f"Нельзя изменять:\n"
                f"  ◻ Сумму перевода\n"
                f"  ◻ Комментарий к переводу\n"
                f"  ◻ Получателя\n"
                f"  ◻ Замораживать платеж\n\n"
                f"После оплаты нажмите на кнопку 'Проверить оплату'"
            )
            kb = payment_check_keyboard(pay_url, payment_id)
            await message.answer(text, reply_markup=kb)
        else:
            await message.answer("❌ Ошибка создания платежа. Проверьте настройки Lolz.")
            await update_payment_status(db, payment_id, "cancelled")

    elif method == "sbp":
        sbp_details = await get_setting(db, "sbp_details") or "Реквизиты не заданы"
        await update_payment_external_id(db, payment_id, f"sbp_{payment_id}")
        amount_int = int(amount) if amount == int(amount) else amount
        text = (
            f"🧊Для оплаты заказа {payment_id} переведите {amount_int}₽🧊\n"
            f"❄️{sbp_details}❄️\n"
            f"💙Сохраните чек!💙\n"
            f"После оплаты нажмите на кнопку \"Я оплатил\""
        )
        kb = sbp_paid_keyboard(payment_id)
        await message.answer(text, reply_markup=kb)

    await state.clear()


# ==================== SBP: "Я оплатил" → ask for receipt ====================

@router.callback_query(F.data.startswith("sbp_paid:"))
async def sbp_user_paid(callback: CallbackQuery, state: FSMContext):
    payment_id = int(callback.data.split(":")[1])
    await state.set_state(TopupStates.waiting_sbp_receipt)
    await state.update_data(sbp_payment_id=payment_id)
    kb = sbp_cancel_keyboard(payment_id)
    await callback.message.edit_text("Пришлите фото чека", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sbp_cancel:"))
async def sbp_user_cancel(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    payment_id = int(callback.data.split(":")[1])
    await update_payment_status(db, payment_id, "cancelled")
    await state.clear()
    await callback.message.edit_text("❌ Оплата отменена.")
    await callback.answer()


@router.message(TopupStates.waiting_sbp_receipt, F.photo)
async def sbp_receipt_received(
    message: Message, db: aiosqlite.Connection, bot: Bot, state: FSMContext,
    franchise: dict | None = None,
):
    data = await state.get_data()
    payment_id = data.get("sbp_payment_id")
    if not payment_id:
        await state.clear()
        return

    payment = await get_payment(db, payment_id)
    if not payment:
        await state.clear()
        await message.answer("❌ Платёж не найден.")
        return

    await state.clear()
    await message.answer(
        f"✅ Заявка на пополнение принята.\n\n"
        f"⏳ Ожидайте проверки платежа"
    )

    # Notify admins with the receipt photo
    user = await get_user(db, message.from_user.id)
    username = f"@{user['username']}" if user and user["username"] else str(message.from_user.id)
    amount_str = format_price(payment["amount"])
    photo_id = message.photo[-1].file_id

    if franchise:
        # Franchise bot — send ONLY to main bot admins for approval
        admin_text = (
            f"🏦 Новый СБП-платёж (франшиза)!\n\n"
            f"👤 Пользователь: {username} (ID: {message.from_user.id})\n"
            f"💰 Сумма: {amount_str}\n"
            f"🆔 ID платежа: {payment_id}\n"
            f"🏪 Франшиза: {franchise['name']}"
        )
        main_bot = get_main_bot() or bot
        kb_admin = sbp_admin_keyboard(payment_id)
        # Download photo from franchise bot and re-upload via main bot
        # (file_id is bot-specific, can't reuse across bots)
        photo_file = None
        if main_bot.id != bot.id:
            try:
                from io import BytesIO
                file = await bot.get_file(photo_id)
                bio = BytesIO()
                await bot.download_file(file.file_path, bio)
                bio.seek(0)
                from aiogram.types import BufferedInputFile
                photo_file = BufferedInputFile(bio.read(), filename="receipt.jpg")
            except Exception:
                photo_file = None
        for admin_id in settings.ADMIN_IDS:
            try:
                if photo_file:
                    await main_bot.send_photo(admin_id, photo=photo_file, caption=admin_text, reply_markup=kb_admin)
                else:
                    await main_bot.send_photo(admin_id, photo=photo_id, caption=admin_text, reply_markup=kb_admin)
            except Exception:
                pass
    else:
        # Main bot — send to platform admins
        admin_text = (
            f"🏦 Новый СБП-платёж!\n\n"
            f"👤 Пользователь: {username} (ID: {message.from_user.id})\n"
            f"💰 Сумма: {amount_str}\n"
            f"🆔 ID платежа: {payment_id}"
        )
        kb = sbp_admin_keyboard(payment_id)
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_photo(admin_id, photo=photo_id, caption=admin_text, reply_markup=kb)
            except Exception:
                pass


@router.message(TopupStates.waiting_sbp_receipt)
async def sbp_receipt_invalid(message: Message):
    await message.answer("Пришлите фото чека")


# ==================== Check payment callback ====================

@router.callback_query(F.data.startswith("check_pay:"))
async def check_payment_callback(callback: CallbackQuery, db: aiosqlite.Connection):
    payment_id = int(callback.data.split(":")[1])
    payment = await get_payment(db, payment_id)

    if not payment:
        await callback.answer("Платёж не найден", show_alert=True)
        return

    if payment["status"] == "paid":
        await callback.answer("✅ Этот платёж уже зачислен!", show_alert=True)
        return

    if payment["method"] == "crypto_bot" and payment["external_id"]:
        crypto_token = await get_setting(db, "crypto_bot_token") or ""
        invoice = await get_invoice_status(int(payment["external_id"]), token=crypto_token)
        if invoice and invoice.get("status") == "paid":
            await update_payment_status(db, payment_id, "paid", raw_data=invoice)
            await update_balance(db, payment["user_id"], payment["amount"])
            await callback.answer("✅ Оплата подтверждена! Баланс пополнен.", show_alert=True)
            await callback.message.edit_text(
                f"✅ Платёж #{payment_id} подтверждён!\n"
                f"💰 Зачислено: {format_price(payment['amount'])}"
            )
            await _notify_admins_topup(payment["user_id"], payment["amount"], "crypto_bot", payment_id, db)
            return

    elif payment["method"] == "lolz" and payment["external_id"]:
        lolz_token = await get_setting(db, "lolz_token") or ""
        paid = await check_lolz_payment(payment["external_id"], token=lolz_token)
        if paid:
            await update_payment_status(db, payment_id, "paid")
            await update_balance(db, payment["user_id"], payment["amount"])
            await callback.answer("✅ Оплата подтверждена! Баланс пополнен.", show_alert=True)
            await callback.message.edit_text(
                f"✅ Платёж #{payment_id} подтверждён!\n"
                f"💰 Зачислено: {format_price(payment['amount'])}"
            )
            await _notify_admins_topup(payment["user_id"], payment["amount"], "lolz", payment_id, db)
            return

    await callback.answer("⏳ Оплата пока не поступила. Попробуйте позже.", show_alert=True)


# ==================== Admin SBP approve/reject ====================

@router.callback_query(AdminSbpCB.filter(F.action == "approve"))
async def sbp_approve(callback: CallbackQuery, callback_data: AdminSbpCB, db: aiosqlite.Connection, bot: Bot):
    payment = await get_payment(db, callback_data.payment_id)
    if not payment:
        await callback.answer("Платёж не найден", show_alert=True)
        return
    if payment["status"] == "paid":
        await callback.answer("Этот платёж уже подтверждён", show_alert=True)
        return

    await update_payment_status(db, callback_data.payment_id, "paid")
    await update_balance(db, payment["user_id"], payment["amount"])

    caption = callback.message.caption or ""
    try:
        await callback.message.edit_caption(
            caption=caption + f"\n\n✅ ПОДТВЕРЖДЕНО @{callback.from_user.username or callback.from_user.id}"
        )
    except Exception:
        pass
    await callback.answer("✅ Платёж подтверждён", show_alert=True)

    # Determine which bot to use for notifying the user
    notify_bot = bot
    if payment["franchise_id"]:
        cursor = await db.execute(
            "SELECT bot_token FROM franchises WHERE id = ?", (payment["franchise_id"],)
        )
        row = await cursor.fetchone()
        if row and row["bot_token"]:
            fb = get_franchise_bot(row["bot_token"])
            if fb:
                notify_bot = fb

    try:
        await notify_bot.send_message(
            payment["user_id"],
            f"✅ Ваш СБП-платёж #{callback_data.payment_id} подтверждён!\n"
            f"💰 Зачислено: {format_price(payment['amount'])}"
        )
    except Exception:
        pass

    await _notify_admins_topup(payment["user_id"], payment["amount"], "sbp", callback_data.payment_id, db)


@router.callback_query(AdminSbpCB.filter(F.action == "reject"))
async def sbp_reject(callback: CallbackQuery, callback_data: AdminSbpCB, db: aiosqlite.Connection, bot: Bot):
    payment = await get_payment(db, callback_data.payment_id)
    if not payment:
        await callback.answer("Платёж не найден", show_alert=True)
        return
    if payment["status"] == "paid":
        await callback.answer("Этот платёж уже подтверждён", show_alert=True)
        return

    await update_payment_status(db, callback_data.payment_id, "cancelled")

    caption = callback.message.caption or ""
    try:
        await callback.message.edit_caption(
            caption=caption + f"\n\n❌ ОТКЛОНЕНО @{callback.from_user.username or callback.from_user.id}"
        )
    except Exception:
        pass
    await callback.answer("❌ Платёж отклонён", show_alert=True)

    # Determine which bot to use for notifying the user
    notify_bot = bot
    if payment["franchise_id"]:
        cursor = await db.execute(
            "SELECT bot_token FROM franchises WHERE id = ?", (payment["franchise_id"],)
        )
        row = await cursor.fetchone()
        if row and row["bot_token"]:
            fb = get_franchise_bot(row["bot_token"])
            if fb:
                notify_bot = fb

    try:
        await notify_bot.send_message(
            payment["user_id"],
            f"❌ Ваш СБП-платёж #{callback_data.payment_id} отклонён.\n"
            f"Обратитесь в поддержку, если считаете это ошибкой."
        )
    except Exception:
        pass


# ==================== Telegram Stars handlers ====================

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, db: aiosqlite.Connection):
    payment_info = message.successful_payment
    payment_id = int(payment_info.invoice_payload)

    payment = await get_payment(db, payment_id)
    if not payment or payment["status"] == "paid":
        return

    await update_payment_status(db, payment_id, "paid", raw_data={
        "telegram_payment_charge_id": payment_info.telegram_payment_charge_id,
        "total_amount": payment_info.total_amount,
        "currency": payment_info.currency,
    })
    await update_balance(db, payment["user_id"], payment["amount"])
    await message.answer(
        f"✅ Оплата Stars прошла успешно!\n"
        f"💰 Зачислено: {format_price(payment['amount'])}"
    )
    await _notify_admins_topup(payment["user_id"], payment["amount"], "stars", payment_id, db)
