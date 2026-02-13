from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

from keyboards.callbacks import (
    CategoryCB, ProductCB, PaymentMethodCB, CryptoCurrencyCB,
    ProfileCB, OrderCB, SubscriptionCB, OfferCB, MainMenuCB,
    AdminPanelCB, AdminCategoryCB, AdminProductCB, AdminPromoCB,
    AdminTextCB, AdminNewsCB, AdminConfirmCB, AdminSbpCB,
    AdminFranchiseCB, FranchisePanelCB, FranchiseProductCB,
    FranchiseSbpCB,
)
from utils.formatting import format_price
from utils.pagination import paginate, add_pagination_row
from config import settings


# === User keyboards ===

def main_menu_inline_keyboard(texts: dict, franchise: dict | None = None, user_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=texts.get("btn_shop", "🛍 Купить"),
            callback_data=MainMenuCB(action="shop").pack(),
        ),
        InlineKeyboardButton(
            text=texts.get("btn_profile", "👤 Профиль"),
            callback_data=MainMenuCB(action="profile").pack(),
        ),
    )
    kb.row(
        InlineKeyboardButton(
            text=texts.get("btn_news", "📌 Новости"),
            callback_data=MainMenuCB(action="news").pack(),
        ),
        InlineKeyboardButton(
            text=texts.get("btn_support", "💎 Саппорт"),
            callback_data=MainMenuCB(action="support").pack(),
        ),
    )
    kb.row(
        InlineKeyboardButton(
            text="❄️ Франшиза",
            callback_data=MainMenuCB(action="franchise").pack(),
        ),
        InlineKeyboardButton(
            text=texts.get("btn_topup", "💰 Пополнить баланс"),
            callback_data=MainMenuCB(action="topup").pack(),
        ),
    )
    kb.row(InlineKeyboardButton(
        text=texts.get("btn_reviews", "⭐Отзывы⭐"),
        callback_data=MainMenuCB(action="reviews").pack(),
    ))
    # Show "Управление" button only for franchise owner
    if franchise and user_id and user_id == franchise["owner_id"]:
        kb.row(InlineKeyboardButton(
            text="⚙️ Управление франшизой",
            callback_data=MainMenuCB(action="manage").pack(),
        ))
    return kb.as_markup()


def subscription_keyboard(channel_username: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    ch = channel_username or settings.CHANNEL_USERNAME
    if ch:
        kb.row(InlineKeyboardButton(
            text="📢 Подписаться",
            url=f"https://t.me/{ch.lstrip('@')}",
        ))
    kb.row(InlineKeyboardButton(
        text="✅ Я подписался",
        callback_data=SubscriptionCB(action="check").pack(),
    ))
    return kb.as_markup()


def offer_keyboard(channel_username: str = "", offer_url: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    ch = channel_username or settings.CHANNEL_USERNAME
    url = offer_url or settings.OFFER_URL
    if ch:
        kb.row(InlineKeyboardButton(
            text="📢 Подписаться на канал",
            url=f"https://t.me/{ch.lstrip('@')}",
        ))
    if url:
        kb.row(InlineKeyboardButton(
            text="📄 Оферта",
            url=url,
        ))
    kb.row(InlineKeyboardButton(
        text="✅ Я согласен с офертой и подписался на канал",
        callback_data=OfferCB(action="agree").pack(),
    ))
    return kb.as_markup()


def categories_keyboard(categories: list, page: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    page_items, total_pages, has_prev, has_next = paginate(categories, page, per_page=8)
    for cat in page_items:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{cat['name']}",
            callback_data=CategoryCB(id=cat["id"], action="view").pack(),
        ))
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "cat")
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def products_keyboard(products: list, page: int = 0, parent_id: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    page_items, total_pages, has_prev, has_next = paginate(products, page, per_page=8)
    for p in page_items:
        if p["is_infinite"]:
            stock = " [♾]"
        elif p["stock_count"] > 0:
            stock = f" [{p['stock_count']} шт]"
        else:
            stock = " [нет в наличии]"
        kb.row(InlineKeyboardButton(
            text=f"{p['name']} — {format_price(p['price'])}{stock}",
            callback_data=ProductCB(id=p["id"], action="view").pack(),
        ))
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "prod")
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=CategoryCB(id=parent_id, action="back").pack(),
    ))
    return kb.as_markup()


def product_detail_keyboard(product_id: int, cat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="🛒 Купить",
        callback_data=ProductCB(id=product_id, action="buy").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=CategoryCB(id=cat_id, action="view").pack(),
    ))
    return kb.as_markup()


def purchase_confirm_keyboard(product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=ProductCB(id=product_id, action="confirm").pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=ProductCB(id=product_id, action="view").pack(),
        ),
    )
    return kb.as_markup()


def payment_methods_keyboard(
    lolz_enabled: bool, crypto_enabled: bool,
    sbp_enabled: bool = False, stars_enabled: bool = False,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if sbp_enabled:
        kb.row(InlineKeyboardButton(
            text="🏦 СБП",
            callback_data=PaymentMethodCB(method="sbp").pack(),
        ))
    if lolz_enabled:
        kb.row(InlineKeyboardButton(
            text="💚 LOLZTEAM",
            callback_data=PaymentMethodCB(method="lolz").pack(),
        ))
    if stars_enabled:
        kb.row(InlineKeyboardButton(
            text="⭐ TELEGRAM STARS",
            callback_data=PaymentMethodCB(method="stars").pack(),
        ))
    if crypto_enabled:
        kb.row(InlineKeyboardButton(
            text="🔑 CryptoBot",
            callback_data=PaymentMethodCB(method="crypto_bot").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def crypto_currency_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    currencies = ["USDT", "BTC", "ETH", "USDC", "TON"]
    row1 = currencies[:3]
    row2 = currencies[3:]
    kb.row(*[InlineKeyboardButton(
        text=c, callback_data=CryptoCurrencyCB(currency=c).pack(),
    ) for c in row1])
    kb.row(*[InlineKeyboardButton(
        text=c, callback_data=CryptoCurrencyCB(currency=c).pack(),
    ) for c in row2])
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=PaymentMethodCB(method="back").pack(),
    ))
    return kb.as_markup()


def payment_check_keyboard(pay_url: str, payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Перейти к оплате", url=pay_url))
    kb.row(InlineKeyboardButton(
        text="Проверить оплату",
        callback_data=f"check_pay:{payment_id}",
    ))
    return kb.as_markup()


def sbp_paid_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="Я оплатил",
        callback_data=f"sbp_paid:{payment_id}",
    ))
    return kb.as_markup()


def sbp_cancel_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="Отменить оплату",
        callback_data=f"sbp_cancel:{payment_id}",
    ))
    return kb.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="💎 Реферальная система",
        callback_data=ProfileCB(action="referral").pack(),
    ))
    kb.row(
        InlineKeyboardButton(
            text="🎟 Промокод",
            callback_data=ProfileCB(action="promo").pack(),
        ),
        InlineKeyboardButton(
            text="⭐ Последние покупки",
            callback_data=ProfileCB(action="purchases").pack(),
        ),
    )
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def orders_keyboard(orders: list, page: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    page_items, total_pages, has_prev, has_next = paginate(orders, page, per_page=5)
    for o in page_items:
        name = o["product_name"] or "Удалённый товар"
        kb.row(InlineKeyboardButton(
            text=f"#{o['id']} | {name} | {format_price(o['total_price'])}",
            callback_data=OrderCB(id=o["id"], action="view").pack(),
        ))
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "orders")
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=ProfileCB(action="back").pack(),
    ))
    return kb.as_markup()


def support_keyboard(support_url: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    url = support_url or settings.SUPPORT_URL
    if url:
        kb.row(InlineKeyboardButton(
            text="⚙️ Тех. Поддержка",
            url=url,
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def reviews_keyboard(reviews_url: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    url = reviews_url or settings.REVIEWS_URL
    if url:
        kb.row(InlineKeyboardButton(
            text="⭐ Отзывы",
            url=url,
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


# === Admin keyboards ===

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📁 Категории", callback_data=AdminPanelCB(section="categories").pack()),
        InlineKeyboardButton(text="📦 Товары", callback_data=AdminPanelCB(section="products").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="📋 Заказы", callback_data=AdminPanelCB(section="orders").pack()),
        InlineKeyboardButton(text="👥 Пользователи", callback_data=AdminPanelCB(section="users").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="🎟 Промокоды", callback_data=AdminPanelCB(section="promos").pack()),
        InlineKeyboardButton(text="💳 Оплата", callback_data=AdminPanelCB(section="payments").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="📝 Тексты", callback_data=AdminPanelCB(section="texts").pack()),
        InlineKeyboardButton(text="📣 Рассылка", callback_data=AdminPanelCB(section="broadcast").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=AdminPanelCB(section="stats").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="🖼 Баннер меню", callback_data=AdminPanelCB(section="banner").pack()),
        InlineKeyboardButton(text="🏪 Франшизы", callback_data=AdminPanelCB(section="franchises").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="🔐 Приватки", callback_data=AdminPanelCB(section="private_channels").pack()),
    )
    return kb.as_markup()


def admin_categories_keyboard(categories: list, is_root: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        status = "✅" if cat["is_active"] else "❌"
        kb.row(
            InlineKeyboardButton(
                text=f"{status} {emoji}{cat['name']}",
                callback_data=AdminCategoryCB(id=cat["id"], action="view").pack(),
            ),
        )
    action = "add_root" if is_root else "add_sub"
    kb.row(InlineKeyboardButton(
        text="➕ Добавить категорию",
        callback_data=AdminCategoryCB(id=0, action=action).pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="main").pack(),
    ))
    return kb.as_markup()


def admin_category_detail_keyboard(cat_id: int, has_parent: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not has_parent:
        kb.row(InlineKeyboardButton(
            text="📂 Подкатегории",
            callback_data=AdminCategoryCB(id=cat_id, action="subcats").pack(),
        ))
    kb.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=AdminCategoryCB(id=cat_id, action="edit").pack(),
        ),
        InlineKeyboardButton(
            text="🔄 Вкл/Выкл",
            callback_data=AdminCategoryCB(id=cat_id, action="toggle").pack(),
        ),
    )
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=AdminCategoryCB(id=cat_id, action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="categories").pack(),
    ))
    return kb.as_markup()


def admin_products_keyboard(products: list, cat_id: int, page: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    page_items, total_pages, has_prev, has_next = paginate(products, page, per_page=8)
    for p in page_items:
        status = "✅" if p["is_active"] else "❌"
        stock_label = "♾" if p["is_infinite"] else f"{p['stock_count']}шт"
        kb.row(InlineKeyboardButton(
            text=f"{status} {p['name']} — {format_price(p['price'])} [{stock_label}]",
            callback_data=AdminProductCB(id=p["id"], action="view").pack(),
        ))
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "aprod")
    kb.row(InlineKeyboardButton(
        text="➕ Добавить товар",
        callback_data=AdminProductCB(id=cat_id, action="add").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="products").pack(),
    ))
    return kb.as_markup()


def admin_product_detail_keyboard(prod_id: int, is_infinite: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=AdminProductCB(id=prod_id, action="edit").pack(),
        ),
        InlineKeyboardButton(
            text="🔄 Вкл/Выкл",
            callback_data=AdminProductCB(id=prod_id, action="toggle").pack(),
        ),
    )
    infinite_label = "📦 Обычный товар" if is_infinite else "♾ Бесконечный товар"
    kb.row(InlineKeyboardButton(
        text=infinite_label,
        callback_data=AdminProductCB(id=prod_id, action="infinite").pack(),
    ))
    if not is_infinite:
        kb.row(InlineKeyboardButton(
            text="📋 Управление товарами (stock)",
            callback_data=AdminProductCB(id=prod_id, action="items").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="📨 Контент для выдачи",
        callback_data=AdminProductCB(id=prod_id, action="delivery").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=AdminProductCB(id=prod_id, action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="products").pack(),
    ))
    return kb.as_markup()


def admin_confirm_keyboard(target: str = "", target_id: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Да",
            callback_data=AdminConfirmCB(action="yes", target=target, target_id=target_id).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Нет",
            callback_data=AdminConfirmCB(action="no", target=target, target_id=target_id).pack(),
        ),
    )
    return kb.as_markup()


def admin_back_keyboard(section: str = "main") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section=section).pack(),
    ))
    return kb.as_markup()


def sbp_admin_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=AdminSbpCB(payment_id=payment_id, action="approve").pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=AdminSbpCB(payment_id=payment_id, action="reject").pack(),
        ),
    )
    return kb.as_markup()


def franchise_sbp_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=FranchiseSbpCB(payment_id=payment_id, action="approve").pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=FranchiseSbpCB(payment_id=payment_id, action="reject").pack(),
        ),
    )
    return kb.as_markup()


# === Admin franchise keyboards ===

def admin_franchises_keyboard(franchises: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in franchises:
        status = "✅" if f["is_active"] else "⏳"
        kb.row(InlineKeyboardButton(
            text=f"{status} {f['name']} (ID:{f['id']})",
            callback_data=AdminFranchiseCB(id=f["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="➕ Создать франшизу",
        callback_data=AdminFranchiseCB(id=0, action="create").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="main").pack(),
    ))
    return kb.as_markup()


def admin_franchise_detail_keyboard(franchise_id: int, is_active: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle_text = "⏸ Деактивировать" if is_active else "▶️ Активировать"
    kb.row(InlineKeyboardButton(
        text=toggle_text,
        callback_data=AdminFranchiseCB(id=franchise_id, action="toggle").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="💰 Комиссии",
        callback_data=AdminFranchiseCB(id=franchise_id, action="rates").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="📊 Статистика",
        callback_data=AdminFranchiseCB(id=franchise_id, action="stats").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=AdminFranchiseCB(id=franchise_id, action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="franchises").pack(),
    ))
    return kb.as_markup()


# === Franchisee panel keyboards ===

def franchise_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📦 Мои товары", callback_data=FranchisePanelCB(action="products").pack()),
        InlineKeyboardButton(text="📊 Статистика", callback_data=FranchisePanelCB(action="stats").pack()),
    )
    kb.row(InlineKeyboardButton(
        text="🔐 Приватки",
        callback_data=FranchisePanelCB(action="private_channels").pack(),
    ))
    kb.row(
        InlineKeyboardButton(text="📋 Заказы", callback_data=FranchisePanelCB(action="orders").pack()),
        InlineKeyboardButton(text="💰 Комиссии", callback_data=FranchisePanelCB(action="commissions").pack()),
    )
    kb.row(
        InlineKeyboardButton(text="💸 Вывод средств", callback_data=FranchisePanelCB(action="withdrawal").pack()),
        InlineKeyboardButton(text="📢 Рассылка", callback_data=FranchisePanelCB(action="broadcast").pack()),
    )
    kb.row(InlineKeyboardButton(
        text="🔧 Техническая поддержка",
        callback_data=FranchisePanelCB(action="tech_support").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def franchise_products_keyboard(products: list, page: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    page_items, total_pages, has_prev, has_next = paginate(products, page, per_page=8)
    for p in page_items:
        status = "✅" if p["is_active"] else "❌"
        stock_label = "♾" if p["is_infinite"] else f"{p['stock_count']}шт"
        kb.row(InlineKeyboardButton(
            text=f"{status} {p['name']} — {format_price(p['price'])} [{stock_label}]",
            callback_data=FranchiseProductCB(id=p["id"], action="view").pack(),
        ))
    add_pagination_row(kb, page, total_pages, has_prev, has_next, "fprod")
    kb.row(InlineKeyboardButton(
        text="➕ Добавить товар",
        callback_data=FranchiseProductCB(id=0, action="add").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="back").pack(),
    ))
    return kb.as_markup()


def franchise_product_detail_keyboard(prod_id: int, is_infinite: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=FranchiseProductCB(id=prod_id, action="edit").pack(),
        ),
        InlineKeyboardButton(
            text="🔄 Вкл/Выкл",
            callback_data=FranchiseProductCB(id=prod_id, action="toggle").pack(),
        ),
    )
    infinite_label = "📦 Обычный товар" if is_infinite else "♾ Бесконечный товар"
    kb.row(InlineKeyboardButton(
        text=infinite_label,
        callback_data=FranchiseProductCB(id=prod_id, action="infinite").pack(),
    ))
    if not is_infinite:
        kb.row(InlineKeyboardButton(
            text="📋 Управление товарами (stock)",
            callback_data=FranchiseProductCB(id=prod_id, action="items").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="📨 Контент для выдачи",
        callback_data=FranchiseProductCB(id=prod_id, action="delivery").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=FranchiseProductCB(id=prod_id, action="delete").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchisePanelCB(action="products").pack(),
    ))
    return kb.as_markup()
