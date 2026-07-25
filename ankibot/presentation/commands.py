from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="/start", description="Start"),
        BotCommand(command="/auth", description="Authenticate with AnkiWeb"),
    ]
    await bot.set_my_commands(commands=commands)
