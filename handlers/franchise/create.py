from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import aiosqlite

from keyboards.callbacks import MainMenuCB
from db.queries.franchises import create_franchise, get_franchise_by_owner
from states.franchise_states import FranchiseCreatePublicStates

router = Router(name="franchise_create_public")

INSTRUCTION_TEXT = (
    "🏪 Франшиза — создай свой магазин!\n\n"
    "Вы можете создать собственную копию этого бота, "
    "продавать наш и свой товар, и зарабатывать на каждой продаже.\n\n"
    "📌 Условия:\n"
    "• Продажа нашего товара — вам 0.5% с каждой продажи\n"
    "• Продажа своего товара — вам 95%, нам 5%\n\n"
    "Для создания франшизы вам понадобится свой Telegram-бот.\n"
    "Следуйте инструкции ниже 👇\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🔹 1. Найти и запустить BotFather\n"
    "🔹 Открыть Telegram 📱\n"
    "🔹 В строке поиска ввести BotFather\n"
    "🔹 Проверить наличие синей галочки ✅ — это гарантия, что работает официальный бот\n"
    "🔹 Нажать кнопку «Запустить» или отправить команду /start\n\n"
    "🔹 2. Создать нового бота\n"
    "🔹 Ввести команду /newbot\n\n"
    "🔹 3. Указать имя бота\n"
    "🔹 BotFather запросит два названия\n"
    "🔹 Имя бота\n"
    "🔹 Отображается в заголовке чата и контактах пользователей\n"
    "🔹 Может содержать любые символы, эмодзи и кириллицу\n"
    "🔹 Пример: «Помощник по заказам 🛒»\n\n"
    "🔹 4. Указать Username бота\n"
    "🔹 Username — уникальный идентификатор для поиска и ссылок\n"
    "🔹 Должен содержать только латинские буквы, цифры и подчёркивания\n"
    "🔹 Обязательно должен заканчиваться на «bot»\n"
    "🔹 Примеры:\n"
    "🔹 order_helper_bot\n"
    "🔹 OrderHelperBot\n\n"
    "🔹 5. Получить токен\n"
    "🔹 После создания бот отправит уникальный токен\n"
    "🔹 Формат токена: 1234567890:AABBccDDeeFFggHH\n"
    "🔹 Токен нужно скопировать и отправить в чат\n"
    "🔹 Никому не передавайте токен — это ключ для управления ботом 🔐\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Когда будете готовы — нажмите кнопку ниже 👇"
)


def _franchise_start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="🚀 Создать франшизу",
        callback_data="franchise_public_start",
    ))
    kb.row(InlineKeyboardButton(
        text="◀️ Назад в меню",
        callback_data=MainMenuCB(action="back").pack(),
    ))
    return kb.as_markup()


def _cancel_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="franchise_public_cancel",
    ))
    return kb.as_markup()


# === Показ инструкции (из главного меню) ===

async def show_franchise_info(callback: CallbackQuery):
    kb = _franchise_start_keyboard()
    try:
        await callback.message.edit_text(
            INSTRUCTION_TEXT, reply_markup=kb,
        )
    except Exception:
        await callback.message.delete()
        await callback.message.answer(
            INSTRUCTION_TEXT, reply_markup=kb,
        )
    await callback.answer()


# === Начало создания ===

@router.callback_query(F.data == "franchise_public_start")
async def start_create(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    # Проверяем, нет ли уже франшизы у пользователя
    existing = await get_franchise_by_owner(db, callback.from_user.id)
    if existing:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data=MainMenuCB(action="back").pack(),
        ))
        text = (
            f"✅ У вас уже есть франшиза «{existing['name']}».\n\n"
            f"Бот: @{existing['bot_username'] or '—'}\n"
            f"Статус: {'✅ Активна' if existing['is_active'] else '⏳ На модерации'}"
        )
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb.as_markup())
        await callback.answer()
        return

    await state.set_state(FranchiseCreatePublicStates.waiting_name)
    text = (
        "🏪 Создание франшизы\n\n"
        "Шаг 1 из 2\n\n"
        "Введите название вашего магазина:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=_cancel_keyboard())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=_cancel_keyboard())
    await callback.answer()


# === Шаг 1: Название ===

@router.message(FranchiseCreatePublicStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Название слишком короткое. Введите ещё раз:")
        return

    name = message.text.strip()
    if len(name) > 64:
        await message.answer("❌ Название слишком длинное (макс. 64 символа). Введите ещё раз:")
        return

    await state.update_data(franchise_name=name)
    await state.set_state(FranchiseCreatePublicStates.waiting_token)
    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2 из 2\n\n"
        "Теперь отправьте токен бота, который вы получили у @BotFather.\n\n"
        "Формат: 1234567890:AABBccDDeeFFggHH",
        reply_markup=_cancel_keyboard(),
    )


# === Шаг 2: Токен ===

@router.message(FranchiseCreatePublicStates.waiting_token)
async def process_token(message: Message, db: aiosqlite.Connection, state: FSMContext):
    if not message.text:
        return

    token = message.text.strip()

    # Валидация токена через Telegram API
    try:
        test_bot = Bot(token=token)
        info = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer(
            "❌ Невалидный токен бота.\n\n"
            "Убедитесь, что вы скопировали токен полностью из сообщения @BotFather.\n"
            "Отправьте токен ещё раз:",
            reply_markup=_cancel_keyboard(),
        )
        return

    data = await state.get_data()
    franchise_name = data["franchise_name"]

    # Создаём франшизу (неактивна, ждёт одобрения админа)
    franchise_id = await create_franchise(
        db,
        owner_id=message.from_user.id,
        bot_token=token,
        bot_username=info.username,
        name=franchise_name,
    )

    await state.clear()

    # Удаляем сообщение с токеном (для безопасности)
    try:
        await message.delete()
    except Exception:
        pass

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ В главное меню",
        callback_data=MainMenuCB(action="back").pack(),
    ))

    await message.answer(
        f"🎉 Франшиза создана!\n\n"
        f"📌 Название: {franchise_name}\n"
        f"🤖 Бот: @{info.username}\n"
        f"🆔 ID франшизы: {franchise_id}\n\n"
        f"⏳ Ваша заявка отправлена на модерацию.\n"
        f"После одобрения администратором бот запустится автоматически.\n\n"
        f"Вы получите уведомление когда франшиза будет активирована.",
        reply_markup=kb.as_markup(),
    )

    # Уведомляем админа о новой заявке
    from config import settings
    try:
        admin_kb = InlineKeyboardBuilder()
        from keyboards.callbacks import AdminFranchiseCB
        admin_kb.row(InlineKeyboardButton(
            text="👁 Посмотреть",
            callback_data=AdminFranchiseCB(id=franchise_id, action="view").pack(),
        ))
        for admin_id in settings.ADMIN_IDS:
            await message.bot.send_message(
                admin_id,
                f"🆕 Новая заявка на франшизу!\n\n"
                f"👤 Пользователь: {message.from_user.full_name} "
                f"(@{message.from_user.username or '—'}, ID: {message.from_user.id})\n"
                f"📌 Название: {franchise_name}\n"
                f"🤖 Бот: @{info.username}\n\n"
                f"Перейдите в админ-панель для одобрения.",
                reply_markup=admin_kb.as_markup(),
            )
    except Exception:
        pass


# === Отмена ===

@router.callback_query(F.data == "franchise_public_cancel")
async def cancel_create(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = _franchise_start_keyboard()
    try:
        await callback.message.edit_text(INSTRUCTION_TEXT, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(INSTRUCTION_TEXT, reply_markup=kb)
    await callback.answer()
