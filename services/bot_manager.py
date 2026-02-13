"""
Dynamic franchise bot manager.
Allows adding new franchise bots to polling without restarting.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

logger = logging.getLogger(__name__)

_dp: Dispatcher | None = None
_main_bot: Bot | None = None
_polling_tasks: dict[str, asyncio.Task] = {}  # token -> task
_bots: dict[str, Bot] = {}  # token -> Bot instance


def init_manager(dp: Dispatcher, main_bot: Bot):
    global _dp, _main_bot
    _dp = dp
    _main_bot = main_bot


def get_main_bot() -> Bot | None:
    """Get the main bot instance for sending admin notifications."""
    return _main_bot


def get_franchise_bot(token: str) -> Bot | None:
    """Get a franchise bot instance by token."""
    return _bots.get(token)


async def _poll_bot(bot: Bot):
    """Simple polling loop for a single bot."""
    offset = None
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update.update_id + 1
                try:
                    await _dp.feed_update(bot=bot, update=update)
                except Exception as e:
                    logger.error(f"Error processing update for bot {bot.id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Polling error for bot {bot.id}: {e}")
            await asyncio.sleep(3)


async def start_franchise_bot(token: str) -> bool:
    """Start polling for a new franchise bot. Returns True on success."""
    if token in _polling_tasks:
        return True  # Already running

    try:
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        info = await bot.get_me()

        commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="shop", description="Магазин"),
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="topup", description="Пополнить баланс"),
            BotCommand(command="manage", description="Управление франшизой"),
        ]
        await bot.set_my_commands(commands)

        # Delete webhook to avoid conflicts
        await bot.delete_webhook(drop_pending_updates=True)

        task = asyncio.create_task(_poll_bot(bot))
        _polling_tasks[token] = task
        _bots[token] = bot
        logger.info(f"Franchise bot started dynamically: @{info.username}")
        return True
    except Exception as e:
        logger.error(f"Failed to start franchise bot: {e}")
        return False


async def stop_franchise_bot(token: str):
    """Stop polling for a franchise bot."""
    task = _polling_tasks.pop(token, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info(f"Franchise bot stopped")
