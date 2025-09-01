from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/login", description="Login to your Anki account"),
        BotCommand(command="/decks", description="Show available decks"),
        BotCommand(command="/add_card", description="Add a new card to a deck"),
        BotCommand(command="/add_from_passage", description="AI-generate optimal cards from text"),
        BotCommand(command="/add_english_word", description="Add English vocabulary card"),
        BotCommand(command="/status", description="Check authentication status"),
        BotCommand(command="/whoami", description="Show user info and admin status"),
    ]
    await bot.set_my_commands(commands=commands)
