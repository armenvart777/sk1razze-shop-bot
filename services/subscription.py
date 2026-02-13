import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


async def is_subscribed(bot: Bot, user_id: int, channel: str) -> bool:
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"Subscription check failed for user {user_id} in {channel}: {e}")
        return False
