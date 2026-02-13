from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminCategoryCB, AdminConfirmCB
from keyboards.inline import (
    admin_categories_keyboard, admin_category_detail_keyboard,
    admin_confirm_keyboard, admin_back_keyboard,
)
from db.queries.categories import (
    get_all_root_categories, get_all_subcategories, get_category,
    create_category, update_category, delete_category, toggle_category,
)
from states.admin_states import AdminCategoryStates, AdminEditCategoryStates

router = Router(name="admin_categories")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "categories"))
async def show_categories(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    cats = await get_all_root_categories(db)
    kb = admin_categories_keyboard(cats, is_root=True)
    try:
        await callback.message.edit_text("📁 Управление категориями:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("📁 Управление категориями:", reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "view"))
async def view_category(callback: CallbackQuery, callback_data: AdminCategoryCB, db: aiosqlite.Connection):
    cat = await get_category(db, callback_data.id)
    if not cat:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    status = "✅ Активна" if cat["is_active"] else "❌ Неактивна"
    emoji = cat["emoji"] + " " if cat["emoji"] else ""
    text = (
        f"📁 Категория: {emoji}{cat['name']}\n"
        f"📊 Статус: {status}\n"
        f"🔢 Порядок: {cat['sort_order']}"
    )
    has_parent = cat["parent_id"] is not None
    kb = admin_category_detail_keyboard(cat["id"], has_parent=has_parent)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminCategoryCB.filter(F.action == "subcats"))
async def show_subcats(callback: CallbackQuery, callback_data: AdminCategoryCB, db: aiosqlite.Connection):
    subcats = await get_all_subcategories(db, callback_data.id)
    kb = admin_categories_keyboard(subcats, is_root=False)
    # Replace "add" action with add_sub pointing to parent
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb_builder = InlineKeyboardBuilder()
    for cat in subcats:
        emoji = cat["emoji"] + " " if cat["emoji"] else ""
        status = "✅" if cat["is_active"] else "❌"
        kb_builder.row(InlineKeyboardButton(
            text=f"{status} {emoji}{cat['name']}",
            callback_data=AdminCategoryCB(id=cat["id"], action="view").pack(),
        ))
    kb_builder.row(InlineKeyboardButton(
        text="➕ Добавить подкатегорию",
        callback_data=AdminCategoryCB(id=callback_data.id, action="add_sub").pack(),
    ))
    kb_builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="categories").pack(),
    ))
    parent = await get_category(db, callback_data.id)
    name = parent["name"] if parent else ""
    try:
        await callback.message.edit_text(f"📂 Подкатегории [{name}]:", reply_markup=kb_builder.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(f"📂 Подкатегории [{name}]:", reply_markup=kb_builder.as_markup())
    await callback.answer()


# === Add category ===
@router.callback_query(AdminCategoryCB.filter(F.action.in_({"add_root", "add_sub"})))
async def start_add_category(callback: CallbackQuery, callback_data: AdminCategoryCB, state: FSMContext):
    parent_id = callback_data.id if callback_data.action == "add_sub" else None
    await state.set_state(AdminCategoryStates.waiting_emoji)
    await state.update_data(parent_id=parent_id)
    try:
        await callback.message.edit_text("Введите эмодзи для категории (или отправьте '-' чтобы пропустить):")
    except Exception:
        await callback.message.delete()
        await callback.message.answer("Введите эмодзи для категории (или отправьте '-' чтобы пропустить):")
    await callback.answer()


@router.message(AdminCategoryStates.waiting_emoji)
async def process_emoji(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте текст. Введите эмодзи или '-' чтобы пропустить:")
        return
    emoji = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(emoji=emoji)
    await state.set_state(AdminCategoryStates.waiting_name)
    await message.answer("Введите название категории:")


@router.message(AdminCategoryStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте текст. Введите название категории:")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminCategoryStates.waiting_sort_order)
    await message.answer("Введите порядок сортировки (число, 0 = по умолчанию):")


@router.message(AdminCategoryStates.waiting_sort_order)
async def process_sort_order(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте число (0 = по умолчанию):")
        return
    try:
        sort_order = int(message.text.strip())
    except ValueError:
        sort_order = 0

    data = await state.get_data()
    cat_id = await create_category(
        db,
        name=data["name"],
        emoji=data.get("emoji", ""),
        parent_id=data.get("parent_id"),
        sort_order=sort_order,
    )
    await state.clear()
    await message.answer(f"✅ Категория '{data['name']}' создана (ID: {cat_id})")

    # Show categories list
    cats = await get_all_root_categories(db)
    kb = admin_categories_keyboard(cats, is_root=True)
    await message.answer("📁 Управление категориями:", reply_markup=kb)


# === Edit ===
@router.callback_query(AdminCategoryCB.filter(F.action == "edit"))
async def start_edit(callback: CallbackQuery, callback_data: AdminCategoryCB, state: FSMContext):
    await state.set_state(AdminEditCategoryStates.waiting_value)
    await state.update_data(cat_id=callback_data.id)
    try:
        await callback.message.edit_text(
            "Введите новое название категории (или '-' чтобы оставить текущее).\n"
            "Формат: эмодзи название\n"
            "Пример: ⭐ FunPay"
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "Введите новое название категории (или '-' чтобы оставить текущее).\n"
            "Формат: эмодзи название\n"
            "Пример: ⭐ FunPay"
        )
    await callback.answer()


@router.message(AdminEditCategoryStates.waiting_value)
async def process_edit(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте текст. Формат: эмодзи название (или '-' чтобы оставить):")
        return
    data = await state.get_data()
    cat_id = data["cat_id"]
    text = message.text.strip()

    if text != "-":
        # Try to split emoji and name
        parts = text.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) <= 4:
            await update_category(db, cat_id, emoji=parts[0], name=parts[1])
        else:
            await update_category(db, cat_id, name=text)

    await state.clear()
    await message.answer("✅ Категория обновлена")

    cats = await get_all_root_categories(db)
    kb = admin_categories_keyboard(cats, is_root=True)
    await message.answer("📁 Управление категориями:", reply_markup=kb)


# === Toggle ===
@router.callback_query(AdminCategoryCB.filter(F.action == "toggle"))
async def toggle_cat(callback: CallbackQuery, callback_data: AdminCategoryCB, db: aiosqlite.Connection):
    await toggle_category(db, callback_data.id)
    cat = await get_category(db, callback_data.id)
    status = "активна" if cat["is_active"] else "неактивна"
    await callback.answer(f"Категория теперь {status}", show_alert=True)

    # Refresh view
    emoji = cat["emoji"] + " " if cat["emoji"] else ""
    status_icon = "✅ Активна" if cat["is_active"] else "❌ Неактивна"
    text = f"📁 Категория: {emoji}{cat['name']}\n📊 Статус: {status_icon}\n🔢 Порядок: {cat['sort_order']}"
    has_parent = cat["parent_id"] is not None
    kb = admin_category_detail_keyboard(cat["id"], has_parent=has_parent)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)


# === Delete ===
@router.callback_query(AdminCategoryCB.filter(F.action == "delete"))
async def confirm_delete(callback: CallbackQuery, callback_data: AdminCategoryCB, state: FSMContext):
    await state.update_data(delete_cat_id=callback_data.id)
    kb = admin_confirm_keyboard("del_cat", callback_data.id)
    try:
        await callback.message.edit_text(
            "⚠️ Вы уверены? Удаление категории удалит все подкатегории и товары внутри.",
            reply_markup=kb,
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            "⚠️ Вы уверены? Удаление категории удалит все подкатегории и товары внутри.",
            reply_markup=kb,
        )
    await callback.answer()


@router.callback_query(AdminConfirmCB.filter((F.target == "del_cat") & (F.action == "yes")))
async def do_delete(callback: CallbackQuery, callback_data: AdminConfirmCB, db: aiosqlite.Connection, state: FSMContext):
    await delete_category(db, callback_data.target_id)
    await state.clear()
    await callback.answer("✅ Категория удалена", show_alert=True)
    cats = await get_all_root_categories(db)
    kb = admin_categories_keyboard(cats, is_root=True)
    try:
        await callback.message.edit_text("📁 Управление категориями:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("📁 Управление категориями:", reply_markup=kb)


@router.callback_query(AdminConfirmCB.filter((F.target == "del_cat") & (F.action == "no")))
async def cancel_delete(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    cats = await get_all_root_categories(db)
    kb = admin_categories_keyboard(cats, is_root=True)
    try:
        await callback.message.edit_text("📁 Управление категориями:", reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer("📁 Управление категориями:", reply_markup=kb)
    await callback.answer()
