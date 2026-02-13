from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from keyboards.callbacks import MainMenuCB

router = Router(name="menu")


@router.callback_query(MainMenuCB.filter(F.action == "shop"))
async def menu_shop(callback: CallbackQuery, db: aiosqlite.Connection):
    from handlers.shop.categories import show_root_categories_cb
    await show_root_categories_cb(callback, db)


@router.callback_query(MainMenuCB.filter(F.action == "profile"))
async def menu_profile(callback: CallbackQuery, db: aiosqlite.Connection):
    from handlers.profile.info import show_profile_cb
    await show_profile_cb(callback, db)


@router.callback_query(MainMenuCB.filter(F.action == "news"))
async def menu_news(callback: CallbackQuery, db: aiosqlite.Connection):
    from handlers.news import show_news_cb
    await show_news_cb(callback, db)


@router.callback_query(MainMenuCB.filter(F.action == "support"))
async def menu_support(callback: CallbackQuery, db: aiosqlite.Connection):
    from handlers.support import show_support_cb
    await show_support_cb(callback, db)


@router.callback_query(MainMenuCB.filter(F.action == "topup"))
async def menu_topup(callback: CallbackQuery, db: aiosqlite.Connection, is_franchise_bot: bool = False):
    from handlers.payment.topup_menu import show_topup_menu_cb
    await show_topup_menu_cb(callback, db, is_franchise_bot=is_franchise_bot)


@router.callback_query(MainMenuCB.filter(F.action == "reviews"))
async def menu_reviews(callback: CallbackQuery, db: aiosqlite.Connection):
    from handlers.reviews import show_reviews_cb
    await show_reviews_cb(callback, db)


@router.callback_query(MainMenuCB.filter(F.action == "franchise"))
async def menu_franchise(callback: CallbackQuery):
    from handlers.franchise.create import show_franchise_info
    await show_franchise_info(callback)


@router.callback_query(MainMenuCB.filter(F.action == "manage"))
async def menu_manage(callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict | None = None):
    if not franchise or callback.from_user.id != franchise["owner_id"]:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    from handlers.franchise.panel import show_panel
    await show_panel(callback, db, franchise)
