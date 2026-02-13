from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminNewsCB
from keyboards.inline import admin_back_keyboard
from db.queries.news import get_all_news, get_news_item, create_news, delete_news, toggle_news
from states.admin_states import AdminNewsStates
from utils.formatting import truncate

router = Router(name="admin_news")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "news"))
async def show_news_list(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    news_list = await get_all_news(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    for n in news_list:
        status = "✅" if n["is_published"] else "❌"
        kb.row(InlineKeyboardButton(
            text=f"{status} {truncate(n['title'], 40)}",
            callback_data=AdminNewsCB(id=n["id"], action="view").pack(),
        ))

    kb.row(InlineKeyboardButton(text="➕ Добавить новость", callback_data="admin_news_create"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text("📰 Управление новостями:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminNewsCB.filter(F.action == "view"))
async def view_news(callback: CallbackQuery, callback_data: AdminNewsCB, db: aiosqlite.Connection):
    item = await get_news_item(db, callback_data.id)
    if not item:
        await callback.answer("Новость не найдена", show_alert=True)
        return

    status = "✅ Опубликована" if item["is_published"] else "❌ Скрыта"
    text = (
        f"📰 {item['title']}\n\n"
        f"{item['content']}\n\n"
        f"📊 Статус: {status}\n"
        f"📅 {item['created_at'][:16]}"
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=AdminNewsCB(id=item["id"], action="toggle").pack()),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=AdminNewsCB(id=item["id"], action="delete").pack()),
    )
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="news").pack()))

    if item["image_file_id"]:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(
                photo=item["image_file_id"], caption=text, reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminNewsCB.filter(F.action == "toggle"))
async def toggle_news_handler(callback: CallbackQuery, callback_data: AdminNewsCB, db: aiosqlite.Connection):
    await toggle_news(db, callback_data.id)
    await callback.answer("✅ Статус обновлён", show_alert=True)


@router.callback_query(AdminNewsCB.filter(F.action == "delete"))
async def delete_news_handler(callback: CallbackQuery, callback_data: AdminNewsCB, db: aiosqlite.Connection):
    await delete_news(db, callback_data.id)
    await callback.answer("✅ Новость удалена", show_alert=True)
    # Refresh list
    news_list = await get_all_news(db)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for n in news_list:
        status = "✅" if n["is_published"] else "❌"
        kb.row(InlineKeyboardButton(
            text=f"{status} {truncate(n['title'], 40)}",
            callback_data=AdminNewsCB(id=n["id"], action="view").pack(),
        ))
    kb.row(InlineKeyboardButton(text="➕ Добавить новость", callback_data="admin_news_create"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    await callback.message.edit_text("📰 Управление новостями:", reply_markup=kb.as_markup())


# === Create news ===
@router.callback_query(F.data == "admin_news_create")
async def start_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminNewsStates.waiting_title)
    await callback.message.edit_text("Введите заголовок новости:")
    await callback.answer()


@router.message(AdminNewsStates.waiting_title)
async def news_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminNewsStates.waiting_content)
    await message.answer("Введите текст новости:")


@router.message(AdminNewsStates.waiting_content)
async def news_content(message: Message, state: FSMContext):
    await state.update_data(content=message.html_text.strip())
    await state.set_state(AdminNewsStates.waiting_image)
    await message.answer("Отправьте фото для новости или '-' чтобы пропустить:")


@router.message(AdminNewsStates.waiting_image)
async def news_image(message: Message, db: aiosqlite.Connection, state: FSMContext):
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        await message.answer("Отправьте фото или '-':")
        return

    data = await state.get_data()
    news_id = await create_news(db, data["title"], data["content"], image_file_id)
    await state.clear()
    await message.answer(f"✅ Новость '{data['title']}' создана (ID: {news_id})")
