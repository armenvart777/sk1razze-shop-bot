from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

from keyboards.callbacks import CategoryCB, PaginationCB
from keyboards.inline import categories_keyboard, products_keyboard
from db.queries.categories import get_root_categories, get_subcategories, get_category
from db.queries.products import get_products_by_category
from db.queries.texts import get_text, get_text_photo

router = Router(name="shop_categories")


async def show_root_categories(message: Message, db: aiosqlite.Connection):
    categories = await get_root_categories(db)
    header = await get_text(db, "shop_header")
    photo = await get_text_photo(db, "shop_header")
    kb = categories_keyboard(categories)
    if photo:
        try:
            await message.answer_photo(photo=photo, caption=header, reply_markup=kb)
        except Exception:
            await message.answer(header, reply_markup=kb)
    else:
        await message.answer(header, reply_markup=kb)


async def show_root_categories_cb(callback: CallbackQuery, db: aiosqlite.Connection):
    categories = await get_root_categories(db)
    header = await get_text(db, "shop_header")
    photo = await get_text_photo(db, "shop_header")
    kb = categories_keyboard(categories)
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=photo, caption=header, reply_markup=kb)
        except Exception:
            await callback.message.answer(header, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(header, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(header, reply_markup=kb)
    await callback.answer()


def _build_subcats_keyboard(subcats, back_id: int = 0):
    kb = InlineKeyboardBuilder()
    for subcat in subcats:
        emoji = subcat["emoji"] + " " if subcat["emoji"] else ""
        kb.row(InlineKeyboardButton(
            text=f"{emoji}{subcat['name']}",
            callback_data=CategoryCB(id=subcat["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Вернуться",
        callback_data=CategoryCB(id=back_id, action="back_root").pack(),
    ))
    return kb.as_markup()


@router.callback_query(CategoryCB.filter(F.action == "view"))
async def view_category(callback: CallbackQuery, callback_data: CategoryCB, db: aiosqlite.Connection, franchise: dict | None = None):
    cat = await get_category(db, callback_data.id)
    if not cat:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    emoji = cat["emoji"] + " " if cat["emoji"] else ""

    if cat["parent_id"] is None:
        # Root category — show subcategories
        subcats = await get_subcategories(db, callback_data.id)
        if subcats:
            text = f"📂 Текущая категория: {emoji}{cat['name']}"
            kb = _build_subcats_keyboard(subcats)
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=kb)
        else:
            # No subcategories — show products directly
            franchise_id = franchise["id"] if franchise else None
            products = await get_products_by_category(db, callback_data.id, franchise_id=franchise_id)
            if products:
                text = f"📂 Текущая категория: {emoji}{cat['name']}"
                kb = products_keyboard(products, parent_id=0)
                try:
                    await callback.message.edit_text(text, reply_markup=kb)
                except Exception:
                    await callback.message.delete()
                    await callback.message.answer(text, reply_markup=kb)
            else:
                await callback.answer("В этой категории пока нет товаров", show_alert=True)
    else:
        # Subcategory — show products
        franchise_id = franchise["id"] if franchise else None
        products = await get_products_by_category(db, callback_data.id, franchise_id=franchise_id)
        if products:
            text = f"📂 Текущая категория: {emoji}{cat['name']}"
            kb = products_keyboard(products, parent_id=cat["parent_id"])
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.answer("В этой категории пока нет товаров", show_alert=True)

    await callback.answer()


@router.callback_query(CategoryCB.filter(F.action == "back"))
async def back_to_parent(callback: CallbackQuery, callback_data: CategoryCB, db: aiosqlite.Connection):
    if callback_data.id == 0:
        # Back to root categories
        categories = await get_root_categories(db)
        header = await get_text(db, "shop_header")
        kb = categories_keyboard(categories)
        try:
            await callback.message.edit_text(header, reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.answer(header, reply_markup=kb)
    else:
        cat = await get_category(db, callback_data.id)
        if cat and cat["parent_id"] is None:
            # Show subcategories of this root category
            subcats = await get_subcategories(db, callback_data.id)
            emoji = cat["emoji"] + " " if cat["emoji"] else ""
            text = f"📂 Текущая категория: {emoji}{cat['name']}"
            kb = _build_subcats_keyboard(subcats)
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=kb)
        else:
            categories = await get_root_categories(db)
            header = await get_text(db, "shop_header")
            kb = categories_keyboard(categories)
            try:
                await callback.message.edit_text(header, reply_markup=kb)
            except Exception:
                await callback.message.delete()
                await callback.message.answer(header, reply_markup=kb)
    await callback.answer()


@router.callback_query(CategoryCB.filter(F.action == "back_root"))
async def back_to_root(callback: CallbackQuery, db: aiosqlite.Connection):
    categories = await get_root_categories(db)
    header = await get_text(db, "shop_header")
    kb = categories_keyboard(categories)
    try:
        await callback.message.edit_text(header, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(header, reply_markup=kb)
    await callback.answer()


@router.callback_query(PaginationCB.filter(F.target == "cat"))
async def paginate_categories(callback: CallbackQuery, callback_data: PaginationCB, db: aiosqlite.Connection):
    categories = await get_root_categories(db)
    header = await get_text(db, "shop_header")
    kb = categories_keyboard(categories, page=callback_data.page)
    try:
        await callback.message.edit_text(header, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()
