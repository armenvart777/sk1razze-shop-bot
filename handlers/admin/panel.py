from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB
from keyboards.inline import admin_panel_keyboard

router = Router(name="admin_panel")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔧 Панель администратора", reply_markup=admin_panel_keyboard())


@router.callback_query(AdminPanelCB.filter(F.section == "main"))
async def admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔧 Панель администратора", reply_markup=admin_panel_keyboard())
    await callback.answer()
