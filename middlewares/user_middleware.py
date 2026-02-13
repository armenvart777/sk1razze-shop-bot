from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from db.queries.users import get_user, create_user, update_user_activity


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_tg = None
        if isinstance(event, Message) and event.from_user:
            user_tg = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_tg = event.from_user

        if user_tg and not user_tg.is_bot:
            db = data["db"]
            user = await get_user(db, user_tg.id)
            if not user:
                referrer_id = data.get("referrer_id")
                await create_user(
                    db,
                    user_id=user_tg.id,
                    username=user_tg.username,
                    first_name=user_tg.first_name,
                    last_name=user_tg.last_name,
                    referrer_id=referrer_id,
                )
                user = await get_user(db, user_tg.id)
            else:
                await update_user_activity(db, user_tg.id, user_tg.username)
            data["user_db"] = user

        return await handler(event, data)
