import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import aiosqlite

from filters.admin_filter import IsAdmin
from keyboards.callbacks import AdminPanelCB, AdminConfirmCB, FranchiseBroadcastCB
from keyboards.inline import admin_confirm_keyboard, admin_back_keyboard
from db.queries.users import get_all_user_ids, get_user_count
from states.admin_states import AdminBroadcastStates
from services.bot_manager import get_franchise_bot

logger = logging.getLogger(__name__)

router = Router(name="admin_broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminPanelCB.filter(F.section == "broadcast"))
async def start_broadcast(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    await state.clear()
    total = await get_user_count(db)
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.edit_text(
        f"📣 Рассылка\n\n"
        f"Всего пользователей: {total}\n\n"
        f"Отправьте сообщение для рассылки (текст или фото с подписью):"
    )
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_message)
async def preview_broadcast(message: Message, db: aiosqlite.Connection, state: FSMContext):
    total = await get_user_count(db)

    if message.photo:
        await state.update_data(
            broadcast_type="photo",
            photo_id=message.photo[-1].file_id,
            caption=message.caption or "",
        )
    elif message.text:
        await state.update_data(broadcast_type="text", text=message.text)
    else:
        await message.answer("Отправьте текст или фото.")
        return

    await state.set_state(AdminBroadcastStates.confirming)
    kb = admin_confirm_keyboard("broadcast", 0)
    await message.answer(
        f"📣 Рассылка будет отправлена {total} пользователям.\n"
        f"Подтвердить?",
        reply_markup=kb,
    )


@router.callback_query(AdminConfirmCB.filter((F.target == "broadcast") & (F.action == "yes")), AdminBroadcastStates.confirming)
async def do_broadcast(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    user_ids = await get_all_user_ids(db)
    success = 0
    failed = 0

    await callback.message.edit_text(f"📣 Рассылка запущена... (0/{len(user_ids)})")

    for i, uid in enumerate(user_ids):
        try:
            if data.get("broadcast_type") == "photo":
                await bot.send_photo(uid, photo=data["photo_id"], caption=data.get("caption"))
            else:
                await bot.send_message(uid, data["text"])
            success += 1
        except Exception:
            failed += 1

        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    await callback.message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Успешно: {success}\n"
        f"❌ Ошибок: {failed}\n"
        f"📊 Всего: {len(user_ids)}"
    )
    await callback.answer()


@router.callback_query(AdminConfirmCB.filter((F.target == "broadcast") & (F.action == "no")))
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена", reply_markup=admin_back_keyboard("main"))
    await callback.answer()


# === Franchise broadcast moderation ===

@router.callback_query(FranchiseBroadcastCB.filter(F.action == "approve"))
async def approve_franchise_broadcast(
    callback: CallbackQuery, callback_data: FranchiseBroadcastCB,
    db: aiosqlite.Connection, bot: Bot,
):
    broadcast_id = callback_data.franchise_id
    cursor = await db.execute(
        "SELECT * FROM franchise_broadcasts WHERE id = ?", (broadcast_id,)
    )
    broadcast = await cursor.fetchone()
    if not broadcast:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if broadcast["status"] != "pending":
        await callback.answer("Эта заявка уже обработана", show_alert=True)
        return

    await db.execute(
        "UPDATE franchise_broadcasts SET status = 'approved' WHERE id = ?",
        (broadcast_id,),
    )
    await db.commit()

    # Get franchise info and bot
    cursor = await db.execute(
        "SELECT * FROM franchises WHERE id = ?", (broadcast["franchise_id"],)
    )
    franchise = await cursor.fetchone()
    if not franchise:
        await callback.answer("Франшиза не найдена", show_alert=True)
        return

    franchise_bot = get_franchise_bot(franchise["bot_token"])

    # Get franchise users
    cursor = await db.execute(
        "SELECT DISTINCT user_id FROM orders WHERE franchise_id = ?",
        (franchise["id"],),
    )
    rows = await cursor.fetchall()
    user_ids = [r["user_id"] for r in rows]

    if not user_ids:
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or callback.message.text or "") + "\n\n✅ ОДОБРЕНО (0 пользователей)"
            )
        except Exception:
            try:
                await callback.message.edit_text(
                    (callback.message.text or "") + "\n\n✅ ОДОБРЕНО (0 пользователей)"
                )
            except Exception:
                pass
        await callback.answer("Нет пользователей для рассылки", show_alert=True)
        return

    # Send broadcast via franchise bot
    send_bot = franchise_bot or bot
    sent = 0
    for i, uid in enumerate(user_ids):
        try:
            if broadcast["message_type"] == "photo" and broadcast["photo_file_id"]:
                await send_bot.send_photo(uid, photo=broadcast["photo_file_id"], caption=broadcast["caption"])
            elif broadcast["text_content"]:
                await send_bot.send_message(uid, broadcast["text_content"])
            sent += 1
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    result_text = f"\n\n✅ ОДОБРЕНО\n📨 Отправлено: {sent}/{len(user_ids)}"
    try:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + result_text
        )
    except Exception:
        try:
            await callback.message.edit_text(
                (callback.message.text or "") + result_text
            )
        except Exception:
            pass
    await callback.answer(f"✅ Рассылка отправлена: {sent}/{len(user_ids)}", show_alert=True)

    # Notify franchise owner
    try:
        notify_bot = franchise_bot or bot
        await notify_bot.send_message(
            broadcast["owner_id"],
            f"✅ Ваша рассылка одобрена!\n📨 Отправлено: {sent}/{len(user_ids)}",
        )
    except Exception:
        pass


@router.callback_query(FranchiseBroadcastCB.filter(F.action == "reject"))
async def reject_franchise_broadcast(
    callback: CallbackQuery, callback_data: FranchiseBroadcastCB,
    db: aiosqlite.Connection, bot: Bot,
):
    broadcast_id = callback_data.franchise_id
    cursor = await db.execute(
        "SELECT * FROM franchise_broadcasts WHERE id = ?", (broadcast_id,)
    )
    broadcast = await cursor.fetchone()
    if not broadcast:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if broadcast["status"] != "pending":
        await callback.answer("Эта заявка уже обработана", show_alert=True)
        return

    await db.execute(
        "UPDATE franchise_broadcasts SET status = 'rejected' WHERE id = ?",
        (broadcast_id,),
    )
    await db.commit()

    try:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n❌ ОТКЛОНЕНО"
        )
    except Exception:
        try:
            await callback.message.edit_text(
                (callback.message.text or "") + "\n\n❌ ОТКЛОНЕНО"
            )
        except Exception:
            pass
    await callback.answer("❌ Рассылка отклонена", show_alert=True)

    # Notify franchise owner
    cursor = await db.execute(
        "SELECT * FROM franchises WHERE id = ?", (broadcast["franchise_id"],)
    )
    franchise = await cursor.fetchone()
    if franchise:
        franchise_bot = get_franchise_bot(franchise["bot_token"])
        try:
            notify_bot = franchise_bot or bot
            await notify_bot.send_message(
                broadcast["owner_id"],
                "❌ Ваша заявка на рассылку была отклонена администратором.",
            )
        except Exception:
            pass
