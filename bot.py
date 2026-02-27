import asyncio
import logging
import os
import sys
import signal

# Configure logging level via env or default to INFO

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import settings
from db.engine import init_db, close_db, get_db
from middlewares.db_middleware import DbMiddleware
from middlewares.franchise_middleware import FranchiseMiddleware
from middlewares.user_middleware import UserMiddleware
from middlewares.throttle_middleware import ThrottleMiddleware
from db.queries.franchises import get_active_franchises
from services.bot_manager import init_manager, start_franchise_bot

# Import routers
from handlers.start import router as start_router
from handlers.shop.categories import router as shop_categories_router
from handlers.shop.product_view import router as product_view_router
from handlers.shop.private_channels import router as shop_private_channels_router
from handlers.payment.topup_menu import router as topup_router
from handlers.profile.info import router as profile_info_router
from handlers.profile.referral import router as profile_referral_router
from handlers.profile.promo import router as profile_promo_router
from handlers.profile.purchases import router as profile_purchases_router
# Admin routers
from handlers.admin.panel import router as admin_panel_router
from handlers.admin.categories import router as admin_categories_router
from handlers.admin.products import router as admin_products_router
from handlers.admin.product_items import router as admin_items_router
from handlers.admin.orders import router as admin_orders_router
from handlers.admin.users import router as admin_users_router
from handlers.admin.promo import router as admin_promo_router
from handlers.admin.texts import router as admin_texts_router
from handlers.admin.broadcast import router as admin_broadcast_router
from handlers.admin.payments_config import router as admin_payments_router
from handlers.admin.statistics import router as admin_stats_router
from handlers.admin.banner import router as admin_banner_router
from handlers.admin.private_channels import router as admin_private_channels_router
from handlers.admin.withdrawals import router as admin_withdrawals_router

# Franchise admin router
from handlers.admin.franchises import router as admin_franchises_router

# Franchise panel routers
from handlers.franchise.panel import router as franchise_panel_router
from handlers.franchise.products import router as franchise_products_router
from handlers.franchise.create import router as franchise_create_router
from handlers.franchise.orders import router as franchise_orders_router
from handlers.franchise.payments import router as franchise_payments_router
from handlers.franchise.private_channels import router as franchise_private_channels_router
from handlers.franchise.withdrawals import router as franchise_withdrawals_router

# Menu dispatcher last (catches callback queries for main menu)
from handlers.menu import router as menu_router


logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь и поддержка"),
        BotCommand(command="shop", description="Магазин"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="topup", description="Пополнить баланс"),
        BotCommand(command="news", description="Новости"),
    ]
    await bot.set_my_commands(commands)


LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot.lock")


def check_single_instance():
    """Prevent multiple bot instances from running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # Check if process is alive
            logger.error(f"Bot already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass  # Old process is dead or OS error (Windows), we can take over

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    def cleanup(*_):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)


async def subscription_checker(bot: Bot):
    """Background task: check expired private channel subscriptions every hour."""
    from services.subscription_manager import process_expired_subscriptions

    while True:
        try:
            await asyncio.sleep(3600)  # Every hour
            db = await get_db()
            count = await process_expired_subscriptions(bot, db)
            if count:
                logger.info(f"Subscription checker: processed {count} expired subscriptions")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Subscription checker error: {e}")
            await asyncio.sleep(60)


async def main():
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env")
        return

    check_single_instance()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares (order: Db -> Franchise -> User -> Throttle)
    # Use outer_middleware so they run for ALL events (including franchise bot via feed_update)
    dp.message.outer_middleware(DbMiddleware())
    dp.callback_query.outer_middleware(DbMiddleware())
    dp.message.outer_middleware(FranchiseMiddleware(settings.BOT_TOKEN))
    dp.callback_query.outer_middleware(FranchiseMiddleware(settings.BOT_TOKEN))
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(ThrottleMiddleware())

    # Register admin routers first (they have IsAdmin filter)
    dp.include_router(admin_panel_router)
    dp.include_router(admin_categories_router)
    dp.include_router(admin_products_router)
    dp.include_router(admin_items_router)
    dp.include_router(admin_orders_router)
    dp.include_router(admin_users_router)
    dp.include_router(admin_promo_router)
    dp.include_router(admin_texts_router)
    dp.include_router(admin_broadcast_router)
    dp.include_router(admin_payments_router)
    dp.include_router(admin_stats_router)
    dp.include_router(admin_banner_router)
    dp.include_router(admin_franchises_router)
    dp.include_router(admin_private_channels_router)
    dp.include_router(admin_withdrawals_router)

    # Register franchise routers
    dp.include_router(franchise_panel_router)
    dp.include_router(franchise_products_router)
    dp.include_router(franchise_create_router)
    dp.include_router(franchise_orders_router)
    dp.include_router(franchise_payments_router)
    dp.include_router(franchise_private_channels_router)
    dp.include_router(franchise_withdrawals_router)

    # Register user routers
    dp.include_router(start_router)
    dp.include_router(shop_categories_router)
    dp.include_router(product_view_router)
    dp.include_router(shop_private_channels_router)
    dp.include_router(topup_router)
    dp.include_router(profile_info_router)
    dp.include_router(profile_referral_router)
    dp.include_router(profile_promo_router)
    dp.include_router(profile_purchases_router)
    # Menu dispatcher last — catches remaining callback queries
    dp.include_router(menu_router)

    # Init DB
    await init_db()
    logger.info("Database initialized")

    # Set bot commands (blue menu button)
    await set_bot_commands(bot)
    logger.info("Bot commands set")

    # Init bot manager for dynamic franchise loading
    init_manager(dp, bot)

    # Load existing franchise bots
    try:
        db = await get_db()
        franchises = await get_active_franchises(db)
        for f in franchises:
            await start_franchise_bot(f["bot_token"])
    except Exception as e:
        logger.warning(f"Failed to load franchise bots: {e}")

    # Start background subscription checker
    sub_checker_task = asyncio.create_task(subscription_checker(bot))

    logger.info("Starting polling...")

    # Start main bot polling
    try:
        await dp.start_polling(bot)
    finally:
        sub_checker_task.cancel()
        try:
            await sub_checker_task
        except asyncio.CancelledError:
            pass
        await close_db()
        await bot.session.close()
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
