import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db.queries.franchises import get_franchise_by_token

logger = logging.getLogger(__name__)


class FranchiseMiddleware(BaseMiddleware):
    """Injects franchise context based on which bot is handling the event."""

    def __init__(self, main_bot_token: str):
        self._main_bot_token = main_bot_token

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        bot = data.get("bot")
        if bot and bot.token != self._main_bot_token:
            db = data.get("db")
            if db:
                franchise = await get_franchise_by_token(db, bot.token)
                if franchise and franchise["is_active"]:
                    data["franchise"] = franchise
                    data["is_franchise_bot"] = True
                else:
                    logger.warning(f"Franchise not found or inactive for bot {bot.id}")
                    data["franchise"] = None
                    data["is_franchise_bot"] = True
            else:
                logger.warning(f"DB not available for franchise bot {bot.id}")
                data["franchise"] = None
                data["is_franchise_bot"] = True
        else:
            data["franchise"] = None
            data["is_franchise_bot"] = False

        return await handler(event, data)
