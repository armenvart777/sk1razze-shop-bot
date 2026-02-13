from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

from keyboards.callbacks import PrivateChannelCB, MainMenuCB
from db.queries.private_channels import get_user_subscriptions

router = Router(name="shop_private_channels")


@router.callback_query(PrivateChannelCB.filter(F.action == "my_subs"))
async def my_subscriptions(
    callback: CallbackQuery, db: aiosqlite.Connection,
):
    subs = await get_user_subscriptions(db, callback.from_user.id)

    if not subs:
        text = "📋 У вас нет активных подписок."
    else:
        lines = ["📋 Ваши активные подписки:\n"]
        for s in subs:
            lines.append(
                f"🔐 {s['channel_name']}\n"
                f"   📅 До: {s['expires_at'][:16]}\n"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="◀️ В меню",
        callback_data=MainMenuCB(action="back").pack(),
    ))

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()
