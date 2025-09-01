import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ankibot.application.protocols import AnkiApiClient
from ankibot.application.user_state import UserState, UserStateManager

logger = logging.getLogger(__name__)

router = Router()

# Global instances (will be set in main.py)
anki_client: AnkiApiClient = None  # type: ignore
user_state_manager: UserStateManager = None  # type: ignore
anki_config: Any = None  # type: ignore


def init_handlers(client: AnkiApiClient, state_manager: UserStateManager, config: Any) -> None:
    """Initialize handlers with dependencies."""
    global anki_client, user_state_manager, anki_config
    anki_client = client
    user_state_manager = state_manager
    anki_config = config


@router.message(CommandStart())
async def start_cmd_handler(message: Message):
    """Handle /start command."""
    await message.answer(
        "🎴 Welcome to AnkiBot!\n\n"
        "I can help you create Anki cards directly from Telegram.\n\n"
        "Commands:\n"
        "/login - Login to your Anki account\n"
        "/decks - Show your decks\n"
        "/add_card - Add a new card\n"
        "/status - Check authentication status"
    )


@router.message(Command("login"))
async def login_cmd_handler(message: Message):
    """Handle /login command."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user_state_manager.reset_session(user_id)

    await message.answer("🔐 Authenticating with your Anki account...")

    try:
        success = await anki_client.authenticate(anki_config.username, anki_config.password)
        if success:
            await message.answer("✅ Successfully logged in to Anki!")
        else:
            await message.answer("❌ Authentication failed. Please check your credentials.")
    except Exception as e:
        logger.error(f"Login error for user {user_id}: {e}")
        await message.answer("❌ An error occurred during login. Please try again later.")


@router.message(Command("status"))
async def status_cmd_handler(message: Message):
    """Handle /status command."""
    try:
        # Try to get decks info to check if authenticated
        decks = await anki_client.get_decks_info()
        if decks:
            await message.answer("✅ You are authenticated and connected to Anki.")
        else:
            await message.answer("❌ Not authenticated. Use /login to authenticate.")
    except Exception as e:
        logger.error(f"Status check error: {e}")
        await message.answer("❌ Unable to check status. Please try /login first.")


@router.message(Command("decks"))
async def decks_cmd_handler(message: Message):
    """Handle /decks command."""
    try:
        info = await anki_client.get_info_for_adding()
        if not info.get("decks"):
            await message.answer("❌ No decks found. Please use /login first.")
            return

        decks_text = "📚 Your Anki Decks:\n\n"
        for deck in info["decks"]:
            decks_text += f"• {deck['name']} (ID: {deck['id']})\n"

        await message.answer(decks_text)
    except Exception as e:
        logger.error(f"Decks error: {e}")
        await message.answer("❌ Unable to fetch decks. Please use /login first.")


@router.message(Command("add_card"))
async def add_card_cmd_handler(message: Message):
    """Handle /add_card command."""
    if not message.from_user:
        return

    user_id = message.from_user.id

    try:
        # Get available decks and note types
        info = await anki_client.get_info_for_adding()
        if not info.get("decks") or not info.get("notetypes"):
            await message.answer("❌ Unable to get deck information. Please use /login first.")
            return

        # Reset session and store deck info
        user_state_manager.reset_session(user_id)
        user_state_manager.update_session(
            user_id,
            state=UserState.WAITING_FOR_DECK_SELECTION,
            available_decks=info["decks"],
            available_notetypes=info["notetypes"],
        )

        # Create inline keyboard for deck selection
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for deck in info["decks"]:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text=deck["name"], callback_data=f"deck_{deck['id']}")]
            )

        await message.answer("📚 Choose a deck for your new card:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Add card error for user {user_id}: {e}")
        await message.answer("❌ Unable to start card creation. Please use /login first.")


@router.callback_query(lambda c: c.data and c.data.startswith("deck_"))
async def deck_selection_handler(callback: CallbackQuery):
    """Handle deck selection."""
    if not callback.from_user or not callback.data:
        return

    user_id = callback.from_user.id
    deck_id = int(callback.data.split("_")[1])

    session = user_state_manager.get_session(user_id)
    if session.state != UserState.WAITING_FOR_DECK_SELECTION:
        await callback.answer("❌ Invalid state for deck selection.")
        return

    # Find selected deck and note type
    selected_deck = None
    for deck in session.available_decks or []:
        if deck["id"] == deck_id:
            selected_deck = deck
            break

    if not selected_deck:
        await callback.answer("❌ Invalid deck selection.")
        return

    # Use the first available note type (usually "Basic")
    notetype = session.available_notetypes[0] if session.available_notetypes else None
    if not notetype:
        await callback.answer("❌ No note types available.")
        return

    # Update session
    user_state_manager.update_session(
        user_id, state=UserState.WAITING_FOR_FRONT, deck_id=deck_id, notetype_id=notetype["id"]
    )

    await callback.message.edit_text(
        f"✅ Selected deck: {selected_deck['name']}\n\n📝 Now send me the **front** of the card:"
    )
    await callback.answer()


@router.message()
async def text_message_handler(message: Message):
    """Handle text messages based on user state."""
    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    session = user_state_manager.get_session(user_id)

    if session.state == UserState.WAITING_FOR_FRONT:
        user_state_manager.update_session(user_id, front=message.text, state=UserState.WAITING_FOR_BACK)
        await message.answer("✅ Front saved!\n\n📝 Now send me the **back** of the card:")

    elif session.state == UserState.WAITING_FOR_BACK:
        user_state_manager.update_session(user_id, back=message.text, state=UserState.WAITING_FOR_TAGS)
        await message.answer(
            "✅ Back saved!\n\n🏷️ Send me tags for the card (space-separated), or send 'skip' for no tags:"
        )

    elif session.state == UserState.WAITING_FOR_TAGS:
        tags = message.text.strip() if message.text.lower() != "skip" else ""

        # Create the card
        try:
            success = await anki_client.add_card(
                front=session.front or "",
                back=session.back or "",
                deck_id=session.deck_id or 0,
                notetype_id=session.notetype_id or 0,
                tags=tags,
            )

            if success:
                await message.answer(
                    "🎉 Card created successfully!\n\n"
                    f"**Front:** {session.front}\n"
                    f"**Back:** {session.back}\n"
                    f"**Tags:** {tags or 'None'}\n\n"
                    "Use /add_card to create another card."
                )
            else:
                await message.answer("❌ Failed to create card. Please try again.")

        except Exception as e:
            logger.error(f"Card creation error for user {user_id}: {e}")
            await message.answer("❌ An error occurred while creating the card.")

        # Reset session
        user_state_manager.reset_session(user_id)

    elif session.state == UserState.IDLE:
        await message.answer("👋 Hi! Use /add_card to create a new Anki card, or /help to see all commands.")
