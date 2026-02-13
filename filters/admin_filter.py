from aiogram.filters import Filter
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, **kwargs) -> bool:
        if isinstance(event, Message):
            return event.from_user and event.from_user.id in settings.ADMIN_IDS
        if isinstance(event, CallbackQuery):
            return event.from_user and event.from_user.id in settings.ADMIN_IDS
        return False
