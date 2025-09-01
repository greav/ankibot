from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Start"),
    ]
    await bot.set_my_commands(commands=commands)
