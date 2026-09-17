from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot) -> None:
    # The everyday commands go first: Telegram lists them in this order, and /word and /snippet
    # are what a learner reaches for many times a day, while the rest is one-off setup.
    commands = [
        BotCommand(command="/word", description="Look up a word and make a vocabulary card"),
        BotCommand(command="/snippet", description="Make cards from a text snippet or screenshot"),
        BotCommand(command="/addcard", description="Add a card to AnkiWeb"),
        BotCommand(command="/decks", description="Choose, create or delete decks"),
        BotCommand(command="/model", description="Choose the model that writes your cards"),
        BotCommand(command="/auth", description="Authenticate with AnkiWeb"),
        BotCommand(command="/cancel", description="Cancel the current action"),
        BotCommand(command="/start", description="Start"),
    ]
    await bot.set_my_commands(commands=commands)
