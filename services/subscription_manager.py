import logging
from datetime import datetime, timedelta
from aiogram import Bot
from db.queries.private_channels import (
    get_expired_subscriptions, deactivate_subscription, get_channel,
)

logger = logging.getLogger(__name__)


async def create_invite_link(bot: Bot, tg_channel_id: int, duration_days: int) -> str | None:
    """Create a one-time invite link for a private channel."""
    try:
        kwargs = {"chat_id": tg_channel_id, "member_limit": 1}
        if duration_days < 365000:
            kwargs["expire_date"] = datetime.now() + timedelta(days=duration_days)
        link = await bot.create_chat_invite_link(**kwargs)
        return link.invite_link
    except Exception as e:
        logger.error(f"Failed to create invite link for channel {tg_channel_id}: {e}")
        return None


async def kick_user_from_channel(bot: Bot, tg_channel_id: int, user_id: int) -> bool:
    """Kick a user from a private channel after subscription expires."""
    try:
        await bot.ban_chat_member(chat_id=tg_channel_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=tg_channel_id, user_id=user_id, only_if_banned=True)
        return True
    except Exception as e:
        logger.error(f"Failed to kick user {user_id} from channel {tg_channel_id}: {e}")
        return False


async def process_expired_subscriptions(bot: Bot, db) -> int:
    """Check and process expired subscriptions. Returns count of processed."""
    expired = await get_expired_subscriptions(db)
    count = 0

    for sub in expired:
        tg_channel_id = sub["tg_channel_id"]
        user_id = sub["user_id"]

        # Kick from channel
        await kick_user_from_channel(bot, tg_channel_id, user_id)

        # Deactivate subscription
        await deactivate_subscription(db, sub["id"])

        # Notify user
        try:
            channel_name = sub["channel_name"]
            await bot.send_message(
                user_id,
                f"🔐 Ваша подписка на канал «{channel_name}» истекла.\n\n"
                f"Вы можете продлить подписку, купив товар повторно в магазине.",
            )
        except Exception:
            pass

        count += 1

    if count:
        logger.info(f"Processed {count} expired subscriptions")

    return count
