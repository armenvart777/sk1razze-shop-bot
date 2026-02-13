from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from keyboards.callbacks import ProductCB
from keyboards.inline import product_detail_keyboard, purchase_confirm_keyboard, payment_methods_keyboard
from db.queries.products import get_product
from db.queries.users import get_user
from db.queries.settings import get_setting
from utils.formatting import format_price

router = Router(name="product_view")


@router.callback_query(ProductCB.filter(F.action == "view"))
async def view_product(callback: CallbackQuery, callback_data: ProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    stock_text = "♾ Всегда в наличии" if product["is_infinite"] else f"{product['stock_count']} шт."
    text = (
        f"{product['name']}\n\n"
        f"{product['description']}\n\n"
        f"💰 Цена: {format_price(product['price'])}\n"
        f"📊 В наличии: {stock_text}"
    )

    kb = product_detail_keyboard(product["id"], product["category_id"])

    if product["image_file_id"]:
        await callback.message.delete()
        try:
            await callback.message.answer_photo(
                photo=product["image_file_id"],
                caption=text,
                reply_markup=kb,
            )
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)

    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "buy"))
async def buy_product(callback: CallbackQuery, callback_data: ProductCB, db: aiosqlite.Connection, is_franchise_bot: bool = False):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    if not product["is_infinite"] and product["stock_count"] <= 0:
        await callback.answer("Товар закончился!", show_alert=True)
        return

    user_db = await get_user(db, callback.from_user.id)
    if not user_db or user_db["balance"] < product["price"]:
        # Insufficient balance — show payment methods
        balance = user_db["balance"] if user_db else 0
        deficit = product["price"] - balance

        lolz_enabled = (await get_setting(db, "payment_lolz_enabled")) == "1"
        crypto_enabled = (await get_setting(db, "payment_crypto_bot_enabled")) == "1"
        sbp_enabled = (await get_setting(db, "payment_sbp_enabled")) == "1"
        stars_enabled = (await get_setting(db, "payment_stars_enabled")) == "1"
        kb = payment_methods_keyboard(lolz_enabled, crypto_enabled, sbp_enabled, stars_enabled)

        text = (
            f"❌ Недостаточно средств!\n\n"
            f"{product['name']}\n"
            f"💰 Цена: {format_price(product['price'])}\n"
            f"💳 Ваш баланс: {format_price(balance)}\n"
            f"💸 Не хватает: {format_price(deficit)}\n\n"
            f"Выберите способ оплаты:"
        )

        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)

        await callback.answer()
        return

    text = (
        f"Подтвердите покупку:\n\n"
        f"{product['name']}\n"
        f"💰 Цена: {format_price(product['price'])}\n"
        f"💳 Ваш баланс: {format_price(user_db['balance'])}\n"
        f"💳 После покупки: {format_price(user_db['balance'] - product['price'])}"
    )

    kb = purchase_confirm_keyboard(product["id"])

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)

    await callback.answer()


@router.callback_query(ProductCB.filter(F.action == "confirm"))
async def confirm_purchase(callback: CallbackQuery, callback_data: ProductCB, db: aiosqlite.Connection, franchise: dict | None = None):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    from services.delivery import process_purchase
    success, msg, order_id = await process_purchase(
        db, callback.bot, callback.from_user.id, product["id"], product["price"],
        franchise=franchise,
    )

    if success:
        await callback.answer("✅ Покупка успешна!", show_alert=True)
        try:
            await callback.message.edit_text(f"✅ {msg}")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(f"✅ {msg}")
    else:
        await callback.answer(f"❌ {msg}", show_alert=True)
