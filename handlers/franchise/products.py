from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.franchise_filter import IsFranchiseOwner
from keyboards.callbacks import FranchiseProductCB, FranchisePanelCB
from keyboards.inline import franchise_products_keyboard, franchise_product_detail_keyboard
from db.queries.products import (
    get_product, get_franchise_products, create_franchise_product,
    update_product, delete_product, update_stock_count,
    add_product_items, get_product_items, delete_unsold_items,
    get_available_item,
)
from db.queries.categories import get_all_root_categories, get_all_subcategories, get_category
from states.franchise_states import FranchiseProductStates, FranchiseEditProductStates, FranchiseItemStates, FranchiseDeliveryStates
from utils.formatting import format_price

router = Router(name="franchise_products")


# ──────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────

def _product_text(product: dict) -> str:
    """Формирует текст карточки товара."""
    status = "✅ Активен" if product["is_active"] else "❌ Неактивен"
    stock_text = "♾ Бесконечный" if product["is_infinite"] else f"{product['stock_count']} шт."
    return (
        f"📦 {product['name']}\n\n"
        f"📝 {product['description']}\n"
        f"💰 Цена: {format_price(product['price'])}\n"
        f"📊 В наличии: {stock_text}\n"
        f"📊 Статус: {status}"
    )


async def _safe_edit(callback: CallbackQuery, text: str, kb):
    """Редактирует сообщение; при ошибке — удаляет и отправляет заново."""
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)


async def _verify_product_ownership(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    product_id: int,
    franchise: dict,
) -> dict | None:
    """Загружает товар и проверяет принадлежность к франшизе.
    Возвращает product-словарь или None (с автоматическим ответом callback)."""
    product = await get_product(db, product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return None
    if product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа к этому товару", show_alert=True)
        return None
    return product


# ──────────────────────────────────────────────
# 1. Добавление товара  (FSM)
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "add"), IsFranchiseOwner())
async def start_add_product(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    cats = await get_all_root_categories(db)
    if not cats:
        await callback.answer("Нет доступных категорий", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for cat in cats:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{cat['name']}",
            callback_data=f"fcat_select:{cat['id']}",
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Отмена",
        callback_data=FranchisePanelCB(action="products").pack(),
    ))

    await state.set_state(FranchiseProductStates.choosing_category)
    await _safe_edit(callback, "📁 Выберите категорию для нового товара:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("fcat_select:"), FranchiseProductStates.choosing_category, IsFranchiseOwner())
async def select_category(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    state: FSMContext,
):
    cat_id = int(callback.data.split(":")[1])

    # Проверяем, есть ли подкатегории
    subcats = await get_all_subcategories(db, cat_id)
    if subcats:
        kb = InlineKeyboardBuilder()
        for sub in subcats:
            emoji = sub["emoji"] + " " if sub["emoji"] else ""
            kb.row(InlineKeyboardButton(
                text=f"{emoji}{sub['name']}",
                callback_data=f"fcat_select:{sub['id']}",
            ))
        kb.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=FranchiseProductCB(id=0, action="add").pack(),
        ))
        cat = await get_category(db, cat_id)
        name = cat["name"] if cat else ""
        await _safe_edit(callback, f"📁 Категория «{name}» — выберите подкатегорию:", kb.as_markup())
        await callback.answer()
        return

    # Подкатегорий нет — фиксируем категорию и переходим к вводу названия
    await state.update_data(category_id=cat_id)
    await state.set_state(FranchiseProductStates.waiting_name)

    cat = await get_category(db, cat_id)
    name = cat["name"] if cat else f"ID {cat_id}"
    await _safe_edit(callback, f"📁 Категория: {name}\n\nВведите название товара:", None)
    await callback.answer()


@router.message(FranchiseProductStates.waiting_name, IsFranchiseOwner())
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(FranchiseProductStates.waiting_description)
    await message.answer("Введите описание товара:")


@router.message(FranchiseProductStates.waiting_description, IsFranchiseOwner())
async def add_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.html_text.strip())
    await state.set_state(FranchiseProductStates.waiting_price)
    await message.answer("Введите цену товара (число):")


@router.message(FranchiseProductStates.waiting_price, IsFranchiseOwner())
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную цену (положительное число):")
        return

    await state.update_data(price=price)
    await state.set_state(FranchiseProductStates.waiting_image)
    await message.answer("Отправьте фото товара или напишите '-' чтобы пропустить:")


@router.message(FranchiseProductStates.waiting_image, IsFranchiseOwner())
async def add_product_image(
    message: Message,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        await message.answer("Отправьте фото или '-' чтобы пропустить:")
        return

    data = await state.get_data()
    prod_id = await create_franchise_product(
        db,
        franchise_id=franchise["id"],
        category_id=data["category_id"],
        name=data["name"],
        description=data["description"],
        price=data["price"],
        image_file_id=image_file_id,
    )
    await state.clear()
    await message.answer(
        f"✅ Товар «{data['name']}» создан (ID: {prod_id})\n"
        f"Теперь добавьте stock через управление товаром."
    )


# ──────────────────────────────────────────────
# 2. Просмотр товара
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "view"), IsFranchiseOwner())
async def view_product(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    text = _product_text(product)
    kb = franchise_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    await _safe_edit(callback, text, kb)
    await callback.answer()


# ──────────────────────────────────────────────
# 3. Редактирование товара (FSM)
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "edit"), IsFranchiseOwner())
async def start_edit(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    await state.set_state(FranchiseEditProductStates.choosing_field)
    await state.update_data(prod_id=callback_data.id)

    kb = InlineKeyboardBuilder()
    for field, label in [("name", "Название"), ("description", "Описание"), ("price", "Цена")]:
        kb.row(InlineKeyboardButton(
            text=label,
            callback_data=f"fedit_field:{field}",
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Отмена",
        callback_data=FranchiseProductCB(id=callback_data.id, action="view").pack(),
    ))
    await _safe_edit(callback, "✏️ Что отредактировать?", kb.as_markup())
    await callback.answer()


@router.callback_query(
    F.data.startswith("fedit_field:"),
    FranchiseEditProductStates.choosing_field,
    IsFranchiseOwner(),
)
async def choose_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(FranchiseEditProductStates.waiting_value)
    labels = {"name": "название", "description": "описание", "price": "цену"}
    await _safe_edit(callback, f"Введите новое {labels.get(field, field)}:", None)
    await callback.answer()


@router.message(FranchiseEditProductStates.waiting_value, IsFranchiseOwner())
async def process_edit_value(
    message: Message,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    data = await state.get_data()
    prod_id = data["prod_id"]
    field = data["edit_field"]
    value = message.html_text.strip() if field == "description" else message.text.strip()

    # Проверяем владение перед изменением
    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await state.clear()
        await message.answer("⛔ Нет доступа к этому товару")
        return

    if field == "price":
        try:
            value = float(value)
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите корректную цену:")
            return

    await update_product(db, prod_id, **{field: value})
    await state.clear()
    await message.answer(f"✅ Товар обновлён")


# ──────────────────────────────────────────────
# 4. Вкл/Выкл товара
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "toggle"), IsFranchiseOwner())
async def toggle_product(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    new_active = 0 if product["is_active"] else 1
    await update_product(db, callback_data.id, is_active=new_active)
    status = "активен" if new_active else "неактивен"
    await callback.answer(f"Товар теперь {status}", show_alert=True)

    # Обновляем карточку
    product = await get_product(db, callback_data.id)
    text = _product_text(product)
    kb = franchise_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    await _safe_edit(callback, text, kb)


# ──────────────────────────────────────────────
# 5. Переключение бесконечного товара
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "infinite"), IsFranchiseOwner())
async def toggle_infinite(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    new_val = 0 if product["is_infinite"] else 1
    await update_product(db, callback_data.id, is_infinite=new_val)
    label = "бесконечный" if new_val else "обычный (по stock)"
    await callback.answer(f"Товар теперь {label}", show_alert=True)

    # Обновляем карточку
    product = await get_product(db, callback_data.id)
    text = _product_text(product)
    kb = franchise_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    await _safe_edit(callback, text, kb)


# ──────────────────────────────────────────────
# 6. Удаление товара
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "delete"), IsFranchiseOwner())
async def confirm_delete(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"fdel_yes:{callback_data.id}",
        ),
        InlineKeyboardButton(
            text="❌ Нет",
            callback_data=f"fdel_no:{callback_data.id}",
        ),
    )
    await _safe_edit(
        callback,
        f"⚠️ Удалить товар «{product['name']}»?\nЭто действие необратимо.",
        kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fdel_yes:"), IsFranchiseOwner())
async def do_delete(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])

    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа к этому товару", show_alert=True)
        return

    await delete_product(db, prod_id)
    await callback.answer("✅ Товар удалён", show_alert=True)

    # Возвращаемся к списку товаров
    products = await get_franchise_products(db, franchise["id"])
    text = f"📦 Ваши товары ({len(products)} шт.):"
    kb = franchise_products_keyboard(products)
    await _safe_edit(callback, text, kb)


@router.callback_query(F.data.startswith("fdel_no:"), IsFranchiseOwner())
async def cancel_delete(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])

    product = await _verify_product_ownership(callback, db, prod_id, franchise)
    if not product:
        return

    text = _product_text(product)
    kb = franchise_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    await _safe_edit(callback, text, kb)
    await callback.answer()


# ──────────────────────────────────────────────
# 7. Управление stock-товарами
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "items"), IsFranchiseOwner())
async def show_items(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    items = await get_product_items(db, callback_data.id)
    available = sum(1 for i in items if not i["is_sold"])
    sold = sum(1 for i in items if i["is_sold"])

    text = (
        f"📋 Stock товара: {product['name']}\n\n"
        f"✅ Доступно: {available}\n"
        f"📦 Продано: {sold}\n"
        f"📊 Всего: {len(items)}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="➕ Добавить товары",
        callback_data=f"fitems_add:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить непроданные",
        callback_data=f"fitems_del:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchiseProductCB(id=callback_data.id, action="view").pack(),
    ))

    await _safe_edit(callback, text, kb.as_markup())
    await callback.answer()


# --- Добавление stock-единиц ---

@router.callback_query(F.data.startswith("fitems_add:"), IsFranchiseOwner())
async def start_add_items(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])

    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа к этому товару", show_alert=True)
        return

    await state.set_state(FranchiseItemStates.waiting_content)
    await state.update_data(prod_id=prod_id, items_added=0)
    await _safe_edit(
        callback,
        "Отправляйте содержимое товаров (по одному сообщению на единицу).\n"
        "Или отправьте несколько строк — каждая строка станет отдельным товаром.\n\n"
        "Когда закончите, отправьте /done",
        None,
    )
    await callback.answer()


@router.message(FranchiseItemStates.waiting_content, IsFranchiseOwner())
async def process_items(
    message: Message,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    if message.text and message.text.strip() == "/done":
        data = await state.get_data()
        prod_id = data["prod_id"]
        count = data.get("items_added", 0)

        # Финальная проверка владения
        product = await get_product(db, prod_id)
        if not product or product["franchise_id"] != franchise["id"]:
            await state.clear()
            await message.answer("⛔ Нет доступа к этому товару")
            return

        await update_stock_count(db, prod_id)
        await state.clear()
        product = await get_product(db, prod_id)
        await message.answer(
            f"✅ Добавлено {count} единиц.\n"
            f"📊 В наличии: {product['stock_count']} шт."
        )
        return

    data = await state.get_data()
    prod_id = data["prod_id"]

    # Проверка владения при каждом сообщении
    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await state.clear()
        await message.answer("⛔ Нет доступа к этому товару")
        return

    if message.text:
        lines = message.text.strip().split("\n")
        count = await add_product_items(db, prod_id, lines)
        total = data.get("items_added", 0) + count
        await state.update_data(items_added=total)
        await message.answer(f"✅ +{count} единиц (всего добавлено: {total}). Продолжайте или /done")
    else:
        await message.answer("Отправьте текстовое содержимое.")


# --- Удаление непроданных stock-единиц ---

@router.callback_query(F.data.startswith("fitems_del:"), IsFranchiseOwner())
async def delete_items(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])

    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа к этому товару", show_alert=True)
        return

    count = await delete_unsold_items(db, prod_id)
    await callback.answer(f"Удалено {count} непроданных единиц", show_alert=True)

    # Обновляем экран stock
    product = await get_product(db, prod_id)
    items = await get_product_items(db, prod_id)
    available = sum(1 for i in items if not i["is_sold"])
    sold = sum(1 for i in items if i["is_sold"])

    text = (
        f"📋 Stock товара: {product['name']}\n\n"
        f"✅ Доступно: {available}\n"
        f"📦 Продано: {sold}\n"
        f"📊 Всего: {len(items)}"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="➕ Добавить товары",
        callback_data=f"fitems_add:{prod_id}",
    ))
    kb.row(InlineKeyboardButton(
        text="🗑 Удалить непроданные",
        callback_data=f"fitems_del:{prod_id}",
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchiseProductCB(id=prod_id, action="view").pack(),
    ))
    await _safe_edit(callback, text, kb.as_markup())


# ──────────────────────────────────────────────
# 8. Контент для выдачи (delivery)
# ──────────────────────────────────────────────

@router.callback_query(FranchiseProductCB.filter(F.action == "delivery"), IsFranchiseOwner())
async def delivery_menu(
    callback: CallbackQuery,
    callback_data: FranchiseProductCB,
    db: aiosqlite.Connection,
    franchise: dict,
):
    product = await _verify_product_ownership(callback, db, callback_data.id, franchise)
    if not product:
        return

    has_text = "✅" if product["delivery_text"] else "❌"
    has_file = "✅" if product["delivery_file_id"] else "❌"

    text = (
        f"📨 Контент для выдачи\n"
        f"📦 {product['name']}\n\n"
        f"Текст: {has_text}\n"
        f"Файл: {has_file}\n\n"
        f"При покупке клиент автоматически получит этот контент."
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="📝 Задать текст",
        callback_data=f"fset_delivery_text:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="📎 Задать файл",
        callback_data=f"fset_delivery_file:{callback_data.id}",
    ))
    if product["delivery_text"] or product["delivery_file_id"]:
        kb.row(InlineKeyboardButton(
            text="🗑 Очистить контент",
            callback_data=f"fclear_delivery:{callback_data.id}",
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchiseProductCB(id=callback_data.id, action="view").pack(),
    ))

    await _safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("fset_delivery_text:"), IsFranchiseOwner())
async def start_set_delivery_text(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])
    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(FranchiseDeliveryStates.waiting_content)
    await state.update_data(prod_id=prod_id, delivery_type="text")
    await _safe_edit(
        callback,
        "📝 Отправьте текст, который получит покупатель после покупки:\n\n"
        "(Это может быть ссылка, инструкция, данные и т.д.)",
        None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fset_delivery_file:"), IsFranchiseOwner())
async def start_set_delivery_file(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])
    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(FranchiseDeliveryStates.waiting_content)
    await state.update_data(prod_id=prod_id, delivery_type="file")
    await _safe_edit(
        callback,
        "📎 Отправьте файл (документ или фото), который получит покупатель после покупки:",
        None,
    )
    await callback.answer()


@router.message(FranchiseDeliveryStates.waiting_content, IsFranchiseOwner())
async def process_delivery_content(
    message: Message,
    db: aiosqlite.Connection,
    state: FSMContext,
    franchise: dict,
):
    data = await state.get_data()
    prod_id = data["prod_id"]
    dtype = data["delivery_type"]

    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await state.clear()
        await message.answer("⛔ Нет доступа к этому товару")
        return

    if dtype == "file":
        if message.document:
            await update_product(db, prod_id, delivery_file_id=message.document.file_id)
            await state.clear()
            await message.answer("✅ Файл для выдачи сохранён!")
        elif message.photo:
            await update_product(db, prod_id, delivery_file_id=message.photo[-1].file_id)
            await state.clear()
            await message.answer("✅ Фото для выдачи сохранено!")
        else:
            await message.answer("❌ Отправьте файл или фото:")
            return
    else:
        if not message.text:
            await message.answer("❌ Отправьте текст:")
            return
        await update_product(db, prod_id, delivery_text=message.html_text.strip())
        await state.clear()
        await message.answer("✅ Текст для выдачи сохранён!")


@router.callback_query(F.data.startswith("fclear_delivery:"), IsFranchiseOwner())
async def clear_delivery(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
    franchise: dict,
):
    prod_id = int(callback.data.split(":")[1])
    product = await get_product(db, prod_id)
    if not product or product["franchise_id"] != franchise["id"]:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await db.execute(
        "UPDATE products SET delivery_text = NULL, delivery_file_id = NULL WHERE id = ?",
        (prod_id,),
    )
    await db.commit()
    await callback.answer("✅ Контент очищен", show_alert=True)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=FranchiseProductCB(id=prod_id, action="view").pack(),
    ))
    await _safe_edit(callback, "✅ Контент для выдачи очищен.", kb.as_markup())
