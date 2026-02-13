from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminProductCB, AdminCategoryCB, AdminConfirmCB
from keyboards.inline import (
    admin_products_keyboard, admin_product_detail_keyboard,
    admin_confirm_keyboard, admin_back_keyboard, InlineKeyboardButton, InlineKeyboardBuilder,
)
from db.queries.categories import get_all_root_categories, get_all_subcategories, get_category
from db.queries.products import (
    get_all_products_by_category, get_product, create_product,
    update_product, delete_product, update_stock_count,
)
from states.admin_states import AdminProductStates, AdminEditProductStates, AdminDeliveryStates
from utils.formatting import format_price

router = Router(name="admin_products")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "products"))
async def show_product_categories(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    # Show root categories to pick from
    cats = await get_all_root_categories(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for cat in cats:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{cat['name']}",
            callback_data=AdminProductCB(id=cat["id"], action="cat_view").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="main").pack(),
    ))
    await callback.message.edit_text("📦 Выберите категорию для управления товарами:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminProductCB.filter(F.action == "cat_view"))
async def show_subcats_for_products(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    subcats = await get_all_subcategories(db, callback_data.id)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    if subcats:
        for sub in subcats:
            emoji = sub["emoji"] + " " if sub["emoji"] else ""
            kb.row(InlineKeyboardButton(
                text=f"{emoji}{sub['name']}",
                callback_data=AdminProductCB(id=sub["id"], action="list").pack(),
            ))
    else:
        # No subcategories — show products directly
        kb.row(InlineKeyboardButton(
            text="📦 Товары этой категории",
            callback_data=AdminProductCB(id=callback_data.id, action="list").pack(),
        ))

    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="products").pack(),
    ))
    cat = await get_category(db, callback_data.id)
    name = cat["name"] if cat else ""
    await callback.message.edit_text(f"📦 Категория [{name}] — выберите подкатегорию:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminProductCB.filter(F.action == "list"))
async def list_products(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    products = await get_all_products_by_category(db, callback_data.id)
    kb = admin_products_keyboard(products, callback_data.id)
    cat = await get_category(db, callback_data.id)
    name = cat["name"] if cat else ""
    await callback.message.edit_text(f"📦 Товары [{name}]:", reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminProductCB.filter(F.action == "view"))
async def view_product(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    status = "✅ Активен" if product["is_active"] else "❌ Неактивен"
    stock_text = "♾ Бесконечный" if product["is_infinite"] else f"{product['stock_count']} шт."
    text = (
        f"📦 {product['name']}\n\n"
        f"📝 {product['description']}\n"
        f"💰 Цена: {format_price(product['price'])}\n"
        f"📊 В наличии: {stock_text}\n"
        f"📊 Статус: {status}"
    )
    kb = admin_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# === Add product ===
@router.callback_query(AdminProductCB.filter(F.action == "add"))
async def start_add_product(callback: CallbackQuery, callback_data: AdminProductCB, state: FSMContext):
    await state.set_state(AdminProductStates.waiting_name)
    await state.update_data(category_id=callback_data.id)
    await callback.message.edit_text("Введите название товара:")
    await callback.answer()


@router.message(AdminProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProductStates.waiting_description)
    await message.answer("Введите описание товара:")


@router.message(AdminProductStates.waiting_description)
async def product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.html_text.strip())
    await state.set_state(AdminProductStates.waiting_price)
    await message.answer("Введите цену товара (число):")


@router.message(AdminProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную цену (положительное число):")
        return

    await state.update_data(price=price)
    await state.set_state(AdminProductStates.waiting_image)
    await message.answer("Отправьте фото товара или напишите '-' чтобы пропустить:")


@router.message(AdminProductStates.waiting_image)
async def product_image(message: Message, db: aiosqlite.Connection, state: FSMContext):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        await message.answer("Отправьте фото или '-' чтобы пропустить:")
        return

    data = await state.get_data()
    prod_id = await create_product(
        db,
        category_id=data["category_id"],
        name=data["name"],
        description=data["description"],
        price=data["price"],
        image_file_id=image_file_id,
    )
    await state.clear()
    await message.answer(
        f"✅ Товар '{data['name']}' создан (ID: {prod_id})\n"
        f"Теперь добавьте stock через управление товаром."
    )


# === Edit ===
@router.callback_query(AdminProductCB.filter(F.action == "edit"))
async def start_edit(callback: CallbackQuery, callback_data: AdminProductCB, state: FSMContext):
    await state.set_state(AdminEditProductStates.choosing_field)
    await state.update_data(prod_id=callback_data.id)

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for field, label in [("name", "Название"), ("description", "Описание"), ("price", "Цена")]:
        kb.row(InlineKeyboardButton(
            text=label,
            callback_data=f"edit_field:{field}",
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Отмена",
        callback_data=AdminPanelCB(section="products").pack(),
    ))
    await callback.message.edit_text("Что отредактировать?", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"), AdminEditProductStates.choosing_field)
async def choose_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(AdminEditProductStates.waiting_value)
    labels = {"name": "название", "description": "описание", "price": "цену"}
    await callback.message.edit_text(f"Введите новое {labels.get(field, field)}:")
    await callback.answer()


@router.message(AdminEditProductStates.waiting_value)
async def process_edit_value(message: Message, db: aiosqlite.Connection, state: FSMContext):
    data = await state.get_data()
    prod_id = data["prod_id"]
    field = data["edit_field"]
    value = message.html_text.strip() if field == "description" else message.text.strip()

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


# === Toggle ===
@router.callback_query(AdminProductCB.filter(F.action == "toggle"))
async def toggle_prod(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if product:
        new_active = 0 if product["is_active"] else 1
        await update_product(db, callback_data.id, is_active=new_active)
        status = "активен" if new_active else "неактивен"
        await callback.answer(f"Товар теперь {status}", show_alert=True)

        product = await get_product(db, callback_data.id)
        status_text = "✅ Активен" if product["is_active"] else "❌ Неактивен"
        stock_text = "♾ Бесконечный" if product["is_infinite"] else f"{product['stock_count']} шт."
        text = (
            f"📦 {product['name']}\n\n"
            f"📝 {product['description']}\n"
            f"💰 Цена: {format_price(product['price'])}\n"
            f"📊 В наличии: {stock_text}\n"
            f"📊 Статус: {status_text}"
        )
        kb = admin_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)


# === Infinite toggle ===
@router.callback_query(AdminProductCB.filter(F.action == "infinite"))
async def toggle_infinite(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    new_val = 0 if product["is_infinite"] else 1
    await update_product(db, callback_data.id, is_infinite=new_val)
    label = "бесконечный" if new_val else "обычный (по stock)"
    await callback.answer(f"Товар теперь {label}", show_alert=True)

    product = await get_product(db, callback_data.id)
    status_text = "✅ Активен" if product["is_active"] else "❌ Неактивен"
    stock_text = "♾ Бесконечный" if product["is_infinite"] else f"{product['stock_count']} шт."
    text = (
        f"📦 {product['name']}\n\n"
        f"📝 {product['description']}\n"
        f"💰 Цена: {format_price(product['price'])}\n"
        f"📊 В наличии: {stock_text}\n"
        f"📊 Статус: {status_text}"
    )
    kb = admin_product_detail_keyboard(product["id"], is_infinite=product["is_infinite"])
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)


# === Delete ===
@router.callback_query(AdminProductCB.filter(F.action == "delete"))
async def confirm_delete(callback: CallbackQuery, callback_data: AdminProductCB):
    kb = admin_confirm_keyboard("del_prod", callback_data.id)
    await callback.message.edit_text("⚠️ Удалить этот товар?", reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminConfirmCB.filter((F.target == "del_prod") & (F.action == "yes")))
async def do_delete(callback: CallbackQuery, callback_data: AdminConfirmCB, db: aiosqlite.Connection):
    await delete_product(db, callback_data.target_id)
    await callback.answer("✅ Товар удалён", show_alert=True)
    await callback.message.edit_text("✅ Товар удалён", reply_markup=admin_back_keyboard("products"))


@router.callback_query(AdminConfirmCB.filter((F.target == "del_prod") & (F.action == "no")))
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено", reply_markup=admin_back_keyboard("products"))
    await callback.answer()


# === Delivery content ===
@router.callback_query(AdminProductCB.filter(F.action == "delivery"))
async def delivery_menu(callback: CallbackQuery, callback_data: AdminProductCB, db: aiosqlite.Connection):
    product = await get_product(db, callback_data.id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    has_text = "✅" if product["delivery_text"] else "❌"
    has_file = "✅" if product["delivery_file_id"] else "❌"

    text = (
        f"📨 Контент для выдачи\n"
        f"📦 {product['name']}\n\n"
        f"Текст: {has_text}\n"
        f"Файл: {has_file}\n\n"
        f"При покупке клиент получит этот контент.\n"
        f"Отправьте текст или файл для настройки:"
    )

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="📝 Задать текст",
        callback_data=f"set_delivery_text:{callback_data.id}",
    ))
    kb.row(InlineKeyboardButton(
        text="📎 Задать файл",
        callback_data=f"set_delivery_file:{callback_data.id}",
    ))
    if product["delivery_text"] or product["delivery_file_id"]:
        kb.row(InlineKeyboardButton(
            text="🗑 Очистить контент",
            callback_data=f"clear_delivery:{callback_data.id}",
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminProductCB(id=callback_data.id, action="view").pack(),
    ))

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("set_delivery_text:"))
async def start_set_delivery_text(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split(":")[1])
    await state.set_state(AdminDeliveryStates.waiting_content)
    await state.update_data(prod_id=prod_id, delivery_type="text")
    await callback.message.edit_text(
        "📝 Отправьте текст, который получит покупатель после покупки:\n\n"
        "(Это может быть ссылка, инструкция, данные поставщика и т.д.)"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_delivery_file:"))
async def start_set_delivery_file(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split(":")[1])
    await state.set_state(AdminDeliveryStates.waiting_content)
    await state.update_data(prod_id=prod_id, delivery_type="file")
    await callback.message.edit_text(
        "📎 Отправьте файл (документ), который получит покупатель после покупки:"
    )
    await callback.answer()


@router.message(AdminDeliveryStates.waiting_content)
async def process_delivery_content(message: Message, db: aiosqlite.Connection, state: FSMContext):
    data = await state.get_data()
    prod_id = data["prod_id"]
    dtype = data["delivery_type"]

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


@router.callback_query(F.data.startswith("clear_delivery:"))
async def clear_delivery(callback: CallbackQuery, db: aiosqlite.Connection):
    prod_id = int(callback.data.split(":")[1])
    await db.execute(
        "UPDATE products SET delivery_text = NULL, delivery_file_id = NULL WHERE id = ?",
        (prod_id,),
    )
    await db.commit()
    await callback.answer("✅ Контент очищен", show_alert=True)
    await callback.message.edit_text("✅ Контент для выдачи очищен.", reply_markup=admin_back_keyboard("products"))
