import logging

from aiogram.filters import Filter
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class IsFranchiseOwner(Filter):
    """Passes only if user is the owner of the current franchise bot."""

    async def __call__(self, event: TelegramObject, **kwargs) -> bool:
        franchise = kwargs.get("franchise")
        if not franchise:
            return False

        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        return user_id is not None and user_id == franchise["owner_id"]
