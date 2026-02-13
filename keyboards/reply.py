from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
from db.queries.texts import get_button_texts


async def main_menu_keyboard(db: aiosqlite.Connection) -> ReplyKeyboardMarkup:
    texts = await get_button_texts(db)
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text=texts.get("btn_shop", "🛒 Купить")),
        KeyboardButton(text=texts.get("btn_profile", "👤 Профиль")),
    )
    kb.row(
        KeyboardButton(text=texts.get("btn_news", "📢 Новости")),
        KeyboardButton(text=texts.get("btn_support", "💎 Саппорт")),
    )
    kb.row(KeyboardButton(text=texts.get("btn_topup", "💰 Пополнить баланс")))
    kb.row(KeyboardButton(text=texts.get("btn_reviews", "⭐ Отзывы")))
    return kb.as_markup(resize_keyboard=True)
