from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminTextCB
from keyboards.inline import admin_back_keyboard
from db.queries.texts import get_all_texts, get_text, update_text, get_text_photo, update_text_photo
from states.admin_states import AdminTextStates
from utils.formatting import truncate

router = Router(name="admin_texts")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# Понятные названия для ключей текстов
FRIENDLY_NAMES = {
    "welcome_message": "👋 Приветствие",
    "offer_text": "📜 Оферта",
    "subscription_required": "🔔 Подписка",
    "main_menu_text": "🏠 Главное меню",
    "shop_header": "🛍 Магазин",
    "profile_template": "👤 Профиль",
    "btn_shop": "🔘 Кнопка «Купить»",
    "btn_profile": "🔘 Кнопка «Профиль»",
    "btn_news": "🔘 Кнопка «Новости»",
    "btn_support": "🔘 Кнопка «Саппорт»",
    "btn_topup": "🔘 Кнопка «Пополнить»",
    "btn_reviews": "🔘 Кнопка «Отзывы»",
    "btn_back": "🔘 Кнопка «Назад»",
    "topup_header": "💰 Пополнение",
    "topup_enter_amount": "💰 Ввод суммы",
    "purchase_success": "✅ Покупка ОК",
    "insufficient_balance": "⛔ Мало средств",
    "support_text": "💎 Поддержка",
    "reviews_text": "⭐ Отзывы",
    "news_text": "📰 Новости",
}


def _friendly(key: str) -> str:
    return FRIENDLY_NAMES.get(key, key)


@router.callback_query(AdminPanelCB.filter(F.section == "texts"))
async def show_texts(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    texts = await get_all_texts(db)
    kb = InlineKeyboardBuilder()

    for t in texts:
        has_photo = "🖼 " if t["photo_file_id"] else ""
        name = _friendly(t["key"])
        kb.row(InlineKeyboardButton(
            text=f"{has_photo}{name}",
            callback_data=AdminTextCB(key=t["key"], action="view").pack(),
        ))

    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=AdminPanelCB(section="main").pack()))
    try:
        await callback.message.edit_text("📝 Управление текстами:", reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer("📝 Управление текстами:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminTextCB.filter(F.action == "view"))
async def view_text(callback: CallbackQuery, callback_data: AdminTextCB, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    current = await get_text(db, callback_data.key)
    photo = await get_text_photo(db, callback_data.key)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="✏️ Изменить текст",
        callback_data=AdminTextCB(key=callback_data.key, action="edit").pack(),
    ))
    kb.row(InlineKeyboardButton(
        text="🖼 Установить фото",
        callback_data=AdminTextCB(key=callback_data.key, action="set_photo").pack(),
    ))
    if photo:
        kb.row(InlineKeyboardButton(
            text="🗑 Удалить фото",
            callback_data=AdminTextCB(key=callback_data.key, action="del_photo").pack(),
        ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminPanelCB(section="texts").pack(),
    ))

    photo_status = "🖼 Фото: установлено" if photo else "🖼 Фото: нет"
    name = _friendly(callback_data.key)
    text = (
        f"📝 {name}\n\n"
        f"Текущее значение:\n{current}\n\n"
        f"{photo_status}"
    )

    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(AdminTextCB.filter(F.action == "edit"))
async def start_edit_text(callback: CallbackQuery, callback_data: AdminTextCB, db: aiosqlite.Connection, state: FSMContext):
    current = await get_text(db, callback_data.key)
    await state.set_state(AdminTextStates.waiting_new_value)
    await state.update_data(text_key=callback_data.key)
    name = _friendly(callback_data.key)
    try:
        await callback.message.edit_text(
            f"📝 Редактирование: {name}\n\n"
            f"Текущее значение:\n{current}\n\n"
            f"Введите новое значение:"
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            f"📝 Редактирование: {name}\n\n"
            f"Текущее значение:\n{current}\n\n"
            f"Введите новое значение:"
        )
    await callback.answer()


@router.message(AdminTextStates.waiting_new_value)
async def process_new_text(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте текст:")
        return
    data = await state.get_data()
    key = data["text_key"]
    await update_text(db, key, message.html_text)
    await state.clear()
    await message.answer(f"✅ Текст «{_friendly(key)}» обновлён")


@router.callback_query(AdminTextCB.filter(F.action == "set_photo"))
async def start_set_photo(callback: CallbackQuery, callback_data: AdminTextCB, state: FSMContext):
    await state.set_state(AdminTextStates.waiting_photo)
    await state.update_data(text_key=callback_data.key)
    name = _friendly(callback_data.key)
    try:
        await callback.message.edit_text(
            f"🖼 Отправьте фото для «{name}»:\n\n"
            f"Или отправьте 'отмена' для отмены"
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            f"🖼 Отправьте фото для «{name}»:\n\n"
            f"Или отправьте 'отмена' для отмены"
        )
    await callback.answer()


@router.message(AdminTextStates.waiting_photo, F.photo)
async def process_text_photo(message: Message, db: aiosqlite.Connection, state: FSMContext):
    data = await state.get_data()
    key = data["text_key"]
    photo_id = message.photo[-1].file_id
    await update_text_photo(db, key, photo_id)
    await state.clear()
    await message.answer(f"✅ Фото для «{_friendly(key)}» установлено")


@router.message(AdminTextStates.waiting_photo)
async def process_text_photo_cancel(message: Message, state: FSMContext):
    if message.text and message.text.lower().strip() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
    else:
        await message.answer("Отправьте фото или напишите 'отмена'")


@router.callback_query(AdminTextCB.filter(F.action == "del_photo"))
async def delete_text_photo(callback: CallbackQuery, callback_data: AdminTextCB, db: aiosqlite.Connection):
    await update_text_photo(db, callback_data.key, None)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(f"✅ Фото для «{_friendly(callback_data.key)}» удалено")
    await callback.answer()
