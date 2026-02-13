from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB
from keyboards.inline import admin_back_keyboard
from db.queries.settings import get_setting, set_setting
from states.admin_states import AdminBannerStates

router = Router(name="admin_banner")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "banner"))
async def admin_banner(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    banner = await get_setting(db, "menu_banner_file_id")

    if banner:
        text = (
            "🖼 Баннер главного меню\n\n"
            "Текущий баннер установлен.\n\n"
            "Отправьте новое фото чтобы заменить, "
            "или напишите «удалить» чтобы убрать баннер."
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(
                photo=banner,
                caption=text,
                reply_markup=admin_back_keyboard("main"),
            )
        except Exception:
            await callback.message.answer(text, reply_markup=admin_back_keyboard("main"))
    else:
        text = (
            "🖼 Баннер главного меню\n\n"
            "Баннер не установлен.\n\n"
            "Отправьте фото чтобы установить баннер меню."
        )
        try:
            await callback.message.edit_text(text, reply_markup=admin_back_keyboard("main"))
        except Exception:
            await callback.message.answer(text, reply_markup=admin_back_keyboard("main"))

    await state.set_state(AdminBannerStates.waiting_photo)
    await callback.answer()


@router.message(AdminBannerStates.waiting_photo, F.photo)
async def banner_photo_received(message: Message, db: aiosqlite.Connection, state: FSMContext):
    file_id = message.photo[-1].file_id
    await set_setting(db, "menu_banner_file_id", file_id)
    await state.clear()
    await message.answer(
        "✅ Баннер меню успешно обновлён!",
        reply_markup=admin_back_keyboard("main"),
    )


@router.message(AdminBannerStates.waiting_photo, F.text.lower() == "удалить")
async def banner_delete(message: Message, db: aiosqlite.Connection, state: FSMContext):
    await set_setting(db, "menu_banner_file_id", "")
    await state.clear()
    await message.answer(
        "✅ Баннер меню удалён.",
        reply_markup=admin_back_keyboard("main"),
    )


@router.message(AdminBannerStates.waiting_photo)
async def banner_invalid(message: Message):
    await message.answer(
        "Отправьте фото для баннера или напишите «удалить».",
    )
