from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InputMediaPhoto
from aiogram.fsm.context import FSMContext
import aiosqlite

from config import settings
from keyboards.callbacks import SubscriptionCB, OfferCB, MainMenuCB
from keyboards.inline import offer_keyboard, main_menu_inline_keyboard, support_keyboard
from db.queries.texts import get_text, get_button_texts
from db.queries.users import get_user, create_user
from db.queries.settings import get_setting
from services.subscription import is_subscribed
from utils.referral import parse_referral

router = Router(name="start")


async def _get_channel_username(db: aiosqlite.Connection) -> str:
    return await get_setting(db, "channel_username") or settings.CHANNEL_USERNAME


@router.message(CommandStart())
async def cmd_start(message: Message, db: aiosqlite.Connection, bot: Bot, state: FSMContext, is_franchise_bot: bool = False, franchise: dict | None = None):
    await state.clear()

    # Parse referral
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        ref_id = parse_referral(args[1])
        if ref_id and ref_id != message.from_user.id:
            user = await get_user(db, message.from_user.id)
            if not user:
                await create_user(
                    db,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    referrer_id=ref_id,
                )

    # Skip subscription check for franchise bots
    if is_franchise_bot:
        await show_main_menu(message, db, franchise=franchise)
        return

    # Check subscription
    channel_username = await get_setting(db, "channel_username") or settings.CHANNEL_USERNAME
    subscribed = await is_subscribed(bot, message.from_user.id, channel_username)
    if not subscribed:
        sub_text = await get_text(db, "subscription_required")
        offer_text = await get_text(db, "offer_text")
        offer_url = await get_setting(db, "offer_url") or settings.OFFER_URL
        text = (
            f"❗ {sub_text}\n\n"
            f"Добро пожаловать в Sk1razze Store! 👋\n\n"
            f"Подписавшись, вы получаете:\n"
            f"✅ Доступ ко всем инструментам\n"
            f"✅ Первые анонсы новых товаров\n"
            f"✅ Скидки и розыгрыши для подписчиков\n"
            f"✅ Поддержку от нашей команды\n\n"
            f"📋 {offer_text}\n"
            f"→ {offer_url}"
        )
        await message.answer(
            text,
            reply_markup=offer_keyboard(channel_username=channel_username, offer_url=offer_url),
            disable_web_page_preview=False,
        )
        return

    await show_main_menu(message, db)


@router.message(Command("help"))
async def cmd_help(message: Message, db: aiosqlite.Connection):
    support_text = await get_text(db, "support_text")
    text = (
        f"ℹ️ Помощь — Sk1razze Store\n\n"
        f"Доступные команды:\n"
        f"/start — Главное меню\n"
        f"/shop — Магазин\n"
        f"/profile — Мой профиль\n"
        f"/topup — Пополнить баланс\n"
        f"/news — Новости\n"
        f"/help — Помощь и поддержка\n\n"
        f"{support_text}"
    )
    url = await get_setting(db, "support_url") or ""
    kb = support_keyboard(support_url=url)
    await message.answer(text, reply_markup=kb)


@router.message(Command("shop"))
async def cmd_shop(message: Message, db: aiosqlite.Connection, bot: Bot, is_franchise_bot: bool = False):
    if not is_franchise_bot:
        ch = await _get_channel_username(db)
        subscribed = await is_subscribed(bot, message.from_user.id, ch)
        if not subscribed:
            await message.answer("❌ Сначала подпишитесь на канал и нажмите /start")
            return
    from handlers.shop.categories import show_root_categories
    await show_root_categories(message, db)


@router.message(Command("profile"))
async def cmd_profile(message: Message, db: aiosqlite.Connection, bot: Bot, is_franchise_bot: bool = False):
    if not is_franchise_bot:
        ch = await _get_channel_username(db)
        subscribed = await is_subscribed(bot, message.from_user.id, ch)
        if not subscribed:
            await message.answer("❌ Сначала подпишитесь на канал и нажмите /start")
            return
    from handlers.profile.info import show_profile
    await show_profile(message, db)


@router.message(Command("topup"))
async def cmd_topup(message: Message, db: aiosqlite.Connection, bot: Bot, is_franchise_bot: bool = False):
    if not is_franchise_bot:
        ch = await _get_channel_username(db)
        subscribed = await is_subscribed(bot, message.from_user.id, ch)
        if not subscribed:
            await message.answer("❌ Сначала подпишитесь на канал и нажмите /start")
            return
    from handlers.payment.topup_menu import show_topup_menu
    await show_topup_menu(message, db, is_franchise_bot=is_franchise_bot)


@router.message(Command("news"))
async def cmd_news(message: Message, db: aiosqlite.Connection, bot: Bot, is_franchise_bot: bool = False):
    if not is_franchise_bot:
        ch = await _get_channel_username(db)
        subscribed = await is_subscribed(bot, message.from_user.id, ch)
        if not subscribed:
            await message.answer("❌ Сначала подпишитесь на канал и нажмите /start")
            return
    from handlers.news import show_news
    await show_news(message, db)


@router.callback_query(SubscriptionCB.filter(F.action == "check"))
async def check_subscription(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    ch = await _get_channel_username(db)
    subscribed = await is_subscribed(bot, callback.from_user.id, ch)
    if not subscribed:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)
        return
    await callback.answer("✅ Подписка подтверждена!")
    await callback.message.delete()
    await show_main_menu(callback.message, db, user_id=callback.from_user.id)


@router.callback_query(OfferCB.filter(F.action == "agree"))
async def agree_offer(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    ch = await _get_channel_username(db)
    subscribed = await is_subscribed(bot, callback.from_user.id, ch)
    if not subscribed:
        await callback.answer("❌ Сначала подпишитесь на канал!", show_alert=True)
        return
    await callback.answer("✅ Добро пожаловать!")
    await callback.message.delete()
    await show_main_menu(callback.message, db, user_id=callback.from_user.id)


@router.callback_query(MainMenuCB.filter(F.action == "back"))
async def back_to_main_menu(callback: CallbackQuery, db: aiosqlite.Connection, franchise: dict | None = None):
    user = await get_user(db, callback.from_user.id)
    username = user["username"] if user else "пользователь"
    welcome = await get_text(db, "welcome_message")
    texts = await get_button_texts(db)
    kb = main_menu_inline_keyboard(texts, franchise=franchise, user_id=callback.from_user.id)
    text = f"💎✨ Привет, @{username}!\n\n{welcome}"

    banner = await get_setting(db, "menu_banner_file_id")
    if banner:
        # Current message might be text or photo — delete and send new
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=banner, caption=text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


async def show_main_menu(message: Message, db: aiosqlite.Connection, user_id: int | None = None, franchise: dict | None = None):
    uid = user_id or message.from_user.id
    user = await get_user(db, uid)
    username = user["username"] if user else "пользователь"
    welcome = await get_text(db, "welcome_message")
    texts = await get_button_texts(db)
    kb = main_menu_inline_keyboard(texts, franchise=franchise, user_id=uid)
    text = f"💎✨ Привет, @{username}!\n\n{welcome}"

    banner = await get_setting(db, "menu_banner_file_id")
    if banner:
        try:
            await message.answer_photo(photo=banner, caption=text, reply_markup=kb)
        except Exception:
            await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)
