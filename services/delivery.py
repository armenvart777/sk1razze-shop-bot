import logging
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot
from db.queries.products import get_available_item, get_product, get_template_item, mark_item_sold, update_stock_count
from db.queries.orders import create_order
from db.queries.users import update_balance, get_user
from db.queries.franchises import record_commission
from db.queries.private_channels import get_channel_by_product_id, create_subscription, get_active_subscription
from services.subscription_manager import create_invite_link
from config import settings
from services.bot_manager import get_main_bot
from utils.formatting import format_price

logger = logging.getLogger(__name__)


async def _send_purchase_notification(
    bot: Bot,
    db: aiosqlite.Connection,
    user_id: int,
    product_name: str,
    price: float,
    order_id: int,
    franchise: dict | None = None,
):
    user = await get_user(db, user_id)
    username = f"@{user['username']}" if user and user["username"] else str(user_id)
    text = (
        f"🛒 Новая покупка!\n\n"
        f"👤 Покупатель: {username}\n"
        f"📦 Товар: {product_name}\n"
        f"💰 Сумма: {format_price(price)}\n"
        f"🆔 Заказ #{order_id}"
    )

    # Use main bot for admin notifications (franchise bot can't message admins)
    main_bot = get_main_bot() or bot
    logger.info(f"Purchase notification: main_bot={main_bot.id if main_bot else None}, bot={bot.id}, admins={settings.ADMIN_IDS}, franchise={bool(franchise)}")
    for admin_id in settings.ADMIN_IDS:
        try:
            await main_bot.send_message(admin_id, text, parse_mode=None)
            logger.info(f"Purchase notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send purchase notification to admin {admin_id}: {e}")

    # Notify franchise owner via main bot (so they see it in the main bot)
    if franchise:
        owner_id = franchise["owner_id"]
        if owner_id not in settings.ADMIN_IDS:
            franchise_text = (
                f"🛒 Новая покупка в вашей франшизе!\n\n"
                f"👤 Покупатель: {username}\n"
                f"📦 Товар: {product_name}\n"
                f"💰 Сумма: {format_price(price)}\n"
                f"🆔 Заказ #{order_id}\n"
                f"🏪 Франшиза: {franchise['name']}"
            )
            try:
                await main_bot.send_message(owner_id, franchise_text, parse_mode=None)
            except Exception as e:
                logger.error(f"Failed to send purchase notification to franchise owner {owner_id}: {e}")


async def _deliver_private_channel(
    bot: Bot, db: aiosqlite.Connection, user_id: int,
    product_id: int, order_id: int,
) -> bool:
    """Check if product is linked to a private channel. If so, deliver invite link.
    Returns True if this was a private channel product, False otherwise."""
    channel = await get_channel_by_product_id(db, product_id)
    if not channel or not channel["is_active"]:
        return False

    # Check if user already has an active subscription
    existing = await get_active_subscription(db, user_id, channel["id"])
    if existing:
        try:
            await bot.send_message(
                user_id,
                f"🔐 Заказ #{order_id}\n\n"
                f"У вас уже есть активная подписка на «{channel['name']}» "
                f"до {existing['expires_at'][:16]}.\n"
                f"Подписка продлена!"
            )
        except Exception:
            pass
        # Extend the existing subscription
        new_expires = (
            datetime.strptime(existing["expires_at"], "%Y-%m-%d %H:%M:%S")
            + timedelta(days=channel["duration_days"])
        ).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE private_subscriptions SET expires_at = ? WHERE id = ?",
            (new_expires, existing["id"]),
        )
        await db.commit()
        return True

    # Generate invite link
    invite_link = await create_invite_link(bot, channel["channel_id"], channel["duration_days"])

    # Calculate expiry
    expires_at = (datetime.now() + timedelta(days=channel["duration_days"])).strftime("%Y-%m-%d %H:%M:%S")

    # Create subscription
    await create_subscription(
        db,
        user_id=user_id,
        channel_id=channel["id"],
        order_id=order_id,
        expires_at=expires_at,
        invite_link=invite_link,
    )

    if invite_link:
        text = (
            f"🔐 Заказ #{order_id}\n\n"
            f"✅ Подписка на «{channel['name']}» оформлена!\n"
            f"📅 Действует до: {expires_at[:16]}\n\n"
            f"🔗 Ваша ссылка для входа:\n{invite_link}\n\n"
            f"Ссылка одноразовая, перейдите по ней сейчас."
        )
    else:
        text = (
            f"🔐 Заказ #{order_id}\n\n"
            f"✅ Подписка на «{channel['name']}» оформлена!\n"
            f"📅 Действует до: {expires_at[:16]}\n\n"
            f"⚠️ Не удалось создать ссылку автоматически. "
            f"Обратитесь в поддержку для получения доступа."
        )

    try:
        await bot.send_message(user_id, text)
    except Exception:
        pass

    return True


async def process_purchase(
    db: aiosqlite.Connection,
    bot: Bot,
    user_id: int,
    product_id: int,
    price: float,
    franchise: dict | None = None,
) -> tuple[bool, str, int | None]:
    """Process purchase: deduct balance, pick item, create order, deliver.
    Returns (success, message, order_id)."""
    logger.info(f">>> process_purchase called: user={user_id}, product_id={product_id}, franchise={bool(franchise)}")
    product = await get_product(db, product_id)
    if not product:
        return False, "Товар не найден.", None

    is_infinite = product["is_infinite"]

    if not is_infinite:
        item = await get_available_item(db, product_id)
        if not item:
            return False, "Товар закончился.", None
    else:
        item = None

    # Deduct balance
    await db.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
        (price, user_id, price),
    )

    # Check if deduction happened
    cursor = await db.execute("SELECT changes()")
    changes = (await cursor.fetchone())[0]
    if changes == 0:
        return False, "Недостаточно средств на балансе.", None

    if item:
        # Regular product — mark item as sold
        await mark_item_sold(db, item["id"], user_id)

    # Create order
    franchise_id = franchise["id"] if franchise else None
    order_id = await create_order(
        db, user_id=user_id, product_id=product_id,
        product_item_id=item["id"] if item else None, total_price=price,
        franchise_id=franchise_id,
    )

    if not is_infinite:
        await update_stock_count(db, product_id)

    # --- Commission calculation ---
    if franchise:
        franchisee_user_id = franchise["owner_id"]

        if product["franchise_id"] is None:
            # Owner's product sold via franchise -> franchisee gets commission_owner_product %
            rate = franchise["commission_owner_product"]
            commission = round(price * rate / 100, 2)
            if commission > 0:
                await update_balance(db, franchisee_user_id, commission)
                await record_commission(
                    db, franchise_id=franchise["id"], order_id=order_id,
                    product_type="owner", sale_amount=price,
                    commission_rate=rate, commission_amount=commission,
                    beneficiary_id=franchisee_user_id,
                )
        else:
            # Franchise's product -> owner gets commission_own_product %, franchisee gets rest
            owner_rate = franchise["commission_own_product"]
            owner_commission = round(price * owner_rate / 100, 2)
            franchisee_amount = round(price - owner_commission, 2)

            if franchisee_amount > 0:
                await update_balance(db, franchisee_user_id, franchisee_amount)
                await record_commission(
                    db, franchise_id=franchise["id"], order_id=order_id,
                    product_type="franchise", sale_amount=price,
                    commission_rate=100 - owner_rate, commission_amount=franchisee_amount,
                    beneficiary_id=franchisee_user_id,
                )
            # Record owner's cut for audit
            if owner_commission > 0:
                await record_commission(
                    db, franchise_id=franchise["id"], order_id=order_id,
                    product_type="franchise_owner_cut", sale_amount=price,
                    commission_rate=owner_rate, commission_amount=owner_commission,
                    beneficiary_id=0,
                )

    # Deliver content to user
    try:
        # Check if this is a private channel product first
        is_private_channel = await _deliver_private_channel(bot, db, user_id, product_id, order_id)
        if not is_private_channel:
            delivered = False

            # 1. Limited stock item with content/file
            if item:
                if item["file_id"]:
                    await bot.send_document(user_id, document=item["file_id"], caption=f"📦 Заказ #{order_id}\n\n{product['name']}")
                    delivered = True
                elif item["content"]:
                    await bot.send_message(user_id, f"📦 Заказ #{order_id}\n\n{item['content']}")
                    delivered = True

            # 2. Product-level delivery content (set via admin)
            if not delivered and product["delivery_file_id"]:
                await bot.send_document(user_id, document=product["delivery_file_id"], caption=f"📦 Заказ #{order_id}\n\n{product['name']}")
                delivered = True
            if not delivered and product["delivery_text"]:
                await bot.send_message(user_id, f"📦 Заказ #{order_id}\n\n{product['delivery_text']}")
                delivered = True

            # 3. Template item (infinite products)
            if not delivered:
                template = await get_template_item(db, product_id)
                if template:
                    if template["file_id"]:
                        await bot.send_document(user_id, document=template["file_id"], caption=f"📦 Заказ #{order_id}\n\n{product['name']}")
                        delivered = True
                    elif template["content"]:
                        await bot.send_message(user_id, f"📦 Заказ #{order_id}\n\n{template['content']}")
                        delivered = True

            # 4. Fallback
            if not delivered:
                await bot.send_message(
                    user_id,
                    f"📦 Заказ #{order_id}\n\n"
                    f"{product['name']}\n\n"
                    f"{product['description']}"
                )
    except Exception:
        pass

    # Send purchase notification
    logger.info(f">>> ABOUT TO SEND NOTIFICATION: order={order_id}, product={product['name']}, franchise={bool(franchise)}")
    try:
        await _send_purchase_notification(
            bot, db, user_id, product["name"], price, order_id, franchise,
        )
        logger.info(f">>> NOTIFICATION SENT SUCCESSFULLY for order={order_id}")
    except Exception as e:
        logger.error(f"_send_purchase_notification failed: {e}", exc_info=True)

    return True, f"Покупка успешна! Заказ #{order_id}", order_id
