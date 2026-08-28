from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="/start", description="Start"),
        BotCommand(command="/auth", description="Authenticate with AnkiWeb"),
        BotCommand(command="/addcard", description="Add a card to AnkiWeb"),
        BotCommand(command="/cancel", description="Cancel the current action"),
    ]
    await bot.set_my_commands(commands=commands)
