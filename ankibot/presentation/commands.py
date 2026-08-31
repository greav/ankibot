from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="/start", description="Start"),
        BotCommand(command="/auth", description="Authenticate with AnkiWeb"),
        BotCommand(command="/decks", description="Choose the deck new cards go to"),
        BotCommand(command="/addcard", description="Add a card to AnkiWeb"),
        BotCommand(command="/snippet", description="Make cards from a text snippet or screenshot"),
        BotCommand(command="/cancel", description="Cancel the current action"),
    ]
    await bot.set_my_commands(commands=commands)
