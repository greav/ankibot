import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ankibot.application.models import CardGenerationRequest, EnglishWordRequest, EnglishWordResponse
from ankibot.application.protocols import AnkiApiClient, OpenAIClient
from ankibot.application.user_state import UserState, UserStateManager

logger = logging.getLogger(__name__)

router = Router()

# Global instances (will be set in main.py)
anki_client: AnkiApiClient = None  # type: ignore
openai_client: OpenAIClient = None  # type: ignore
user_state_manager: UserStateManager = None  # type: ignore
anki_config: Any = None  # type: ignore
openai_config: Any = None  # type: ignore


def init_handlers(
    anki_api_client: AnkiApiClient,
    openai_api_client: OpenAIClient,
    state_manager: UserStateManager,
    anki_cfg: Any,
    openai_cfg: Any,
) -> None:
    """Initialize handlers with dependencies."""
    global anki_client, openai_client, user_state_manager, anki_config, openai_config
    anki_client = anki_api_client
    openai_client = openai_api_client
    user_state_manager = state_manager
    anki_config = anki_cfg
    openai_config = openai_cfg


@router.message(CommandStart())
async def start_cmd_handler(message: Message):
    """Handle /start command."""
    await message.answer(
        "🎴 Welcome to AnkiBot!\n\n"
        "I can help you create Anki cards directly from Telegram.\n\n"
        "Commands:\n"
        "/login - Login to your Anki account\n"
        "/decks - Show your decks\n"
        "/add_card - Add a new card manually\n"
        "/add_from_passage - Generate cards from text passage\n"
        "/add_english_word - Add English vocabulary card\n"
        "/status - Check authentication status\n"
        "/whoami - Show user info and admin status"
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


@router.message(Command("whoami"))
async def whoami_cmd_handler(message: Message):
    """Handle /whoami command - show user info and admin status."""
    if not message.from_user:
        await message.answer("❌ Unable to determine user information.")
        return

    user = message.from_user
    user_info = "👤 **User Information**\n\n"
    user_info += f"**ID:** `{user.id}`\n"
    user_info += f"**First Name:** {user.first_name}\n"

    if user.last_name:
        user_info += f"**Last Name:** {user.last_name}\n"

    if user.username:
        user_info += f"**Username:** @{user.username}\n"

    user_info += f"**Language:** {user.language_code or 'Unknown'}\n"
    user_info += "**Bot Admin:** ✅ Yes\n"

    await message.answer(user_info)


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


@router.message(Command("add_from_passage"))
async def add_from_passage_cmd_handler(message: Message):
    """Handle /add_from_passage command."""
    if not message.from_user:
        return

    user_id = message.from_user.id

    try:
        # Check if we can authenticate (basic check)
        info = await anki_client.get_info_for_adding()
        if not info.get("decks") or not info.get("notetypes"):
            await message.answer("❌ Unable to get deck information. Please use /login first.")
            return

        # Reset session and store deck info
        user_state_manager.reset_session(user_id)
        user_state_manager.update_session(
            user_id,
            state=UserState.WAITING_FOR_PASSAGE,
            available_decks=info["decks"],
            available_notetypes=info["notetypes"],
        )

        await message.answer(
            "📖 **Generate Cards from Passage**\n\n"
            "Send me a text passage and I'll analyze it to generate the optimal number of Anki cards using AI.\n\n"
            f"The AI will decide how many cards to create (up to {openai_config.max_cards}) "
            "based on the content richness and complexity.\n\n"
            "Please paste or type the text you want to create cards from:"
        )

    except Exception as e:
        logger.error(f"Add from passage error for user {user_id}: {e}")
        await message.answer("❌ Unable to start passage processing. Please use /login first.")


@router.message(Command("add_english_word"))
async def add_english_word_cmd_handler(message: Message):
    """Handle /add_english_word command."""
    if not message.from_user:
        return

    user_id = message.from_user.id

    try:
        # Check if we can authenticate (basic check)
        info = await anki_client.get_info_for_adding()
        if not info.get("decks") or not info.get("notetypes"):
            await message.answer("❌ Unable to get deck information. Please use /login first.")
            return

        # Reset session and store deck info
        user_state_manager.reset_session(user_id)
        user_state_manager.update_session(
            user_id,
            state=UserState.WAITING_FOR_ENGLISH_WORD,
            available_decks=info["decks"],
            available_notetypes=info["notetypes"],
        )

        await message.answer(
            "🔤 **Generate English Word Card**\n\n"
            "Send me an English word or phrase and I'll create a comprehensive vocabulary card with:\n"
            "• Definition and usage context\n"
            "• Part of speech and synonyms\n"
            "• Situations where it's used\n"
            "• Russian translations\n"
            "• Example sentences with meanings\n\n"
            "Please type the English word or phrase you want to learn:"
        )

    except Exception as e:
        logger.error(f"Add English word error for user {user_id}: {e}")
        await message.answer("❌ Unable to start English word processing. Please use /login first.")


@router.callback_query(lambda c: c.data and c.data.startswith("english_deck_"))
async def english_deck_selection_handler(callback: CallbackQuery):
    """Handle deck selection for English word cards."""
    if not callback.from_user or not callback.data:
        return

    user_id = callback.from_user.id
    deck_id = int(callback.data.split("_")[2])  # english_deck_{id}

    session = user_state_manager.get_session(user_id)
    if session.state != UserState.REVIEWING_ENGLISH_WORD_CARD:
        await callback.answer("❌ Invalid state for English word deck selection.")
        return

    # Find selected deck
    selected_deck = None
    for deck in session.available_decks or []:
        if deck["id"] == deck_id:
            selected_deck = deck
            break

    if not selected_deck:
        await callback.answer("❌ Invalid deck selection.")
        return

    # Find the "English Words Context" note type
    english_notetype = None
    for notetype in session.available_notetypes or []:
        if notetype["name"] == "English Words Context":
            english_notetype = notetype
            break

    if not english_notetype:
        await callback.answer("❌ 'English Words Context' note type not found. Please create it in Anki first.")
        return

    # Create the English word card
    try:
        card = session.generated_english_card
        if not card:
            await callback.answer("❌ No generated card found.")
            return

        # Map fields to the note type
        # Assuming the fields in "English Words Context" note type match our model fields
        success = await anki_client.add_card_with_fields(
            deck_id=deck_id,
            notetype_id=english_notetype["id"],
            fields={
                "Word": card.word,
                "Definition": card.definition,
                "Part of Speech": card.part_of_speech,
                "Synonyms": card.synonyms,
                "Situations to Use It": card.situations_to_use,
                "Russian Translations": card.russian_translations,
                "Example Sentences": card.example_sentences,
                "Sound": "",
            },
            tags="english vocabulary",
        )

        if success:
            await callback.message.edit_text(
                f"🎉 **English word card created successfully!**\n\n"
                f"**Word:** {card.word}\n"
                f"**Deck:** {selected_deck['name']}\n\n"
                "Use /add_english_word to create another vocabulary card."
            )
        else:
            await callback.answer("❌ Failed to create the card. Please try again.")

    except Exception as e:
        logger.error(f"English word card creation error for user {user_id}: {e}")
        await callback.answer("❌ An error occurred while creating the card.")

    # Reset session
    user_state_manager.reset_session(user_id)


@router.callback_query(lambda c: c.data and c.data.startswith("deck_"))
async def deck_selection_handler(callback: CallbackQuery):
    """Handle deck selection."""
    if not callback.from_user or not callback.data:
        return

    user_id = callback.from_user.id
    deck_id = int(callback.data.split("_")[1])

    session = user_state_manager.get_session(user_id)
    if session.state not in [UserState.WAITING_FOR_DECK_SELECTION, UserState.WAITING_FOR_PASSAGE_DECK_SELECTION]:
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

    # Handle different flows based on current state
    if session.state == UserState.WAITING_FOR_DECK_SELECTION:
        # Regular manual card creation flow
        user_state_manager.update_session(
            user_id, state=UserState.WAITING_FOR_FRONT, deck_id=deck_id, notetype_id=notetype["id"]
        )

        await callback.message.edit_text(
            f"✅ Selected deck: {selected_deck['name']}\n\n📝 Now send me the **front** of the card:"
        )

    elif session.state == UserState.WAITING_FOR_PASSAGE_DECK_SELECTION:
        # Passage-based card creation flow
        user_state_manager.update_session(
            user_id, state=UserState.REVIEWING_GENERATED_CARDS, deck_id=deck_id, notetype_id=notetype["id"]
        )

        # Start creating cards from the generated cards list
        await _create_cards_from_generated(callback.message, user_id)

    await callback.answer()


async def _create_cards_from_generated(message: Message, user_id: int) -> None:
    """Helper function to create cards from generated cards list."""
    session = user_state_manager.get_session(user_id)

    if not session.cards_to_create:
        await message.edit_text("❌ No cards to create.")
        return

    success_count = 0
    total_cards = len(session.cards_to_create)

    for card in session.cards_to_create:
        try:
            tags_str = " ".join(card.tags) if card.tags else ""
            success = await anki_client.add_card(
                front=card.front,
                back=card.back,
                deck_id=session.deck_id or 0,
                notetype_id=session.notetype_id or 0,
                tags=tags_str,
            )
            if success:
                success_count += 1
        except Exception as e:
            logger.error(f"Error creating card: {e}")

    await message.edit_text(
        f"🎉 **Cards Created Successfully!**\n\n"
        f"✅ {success_count}/{total_cards} cards added to your deck\n\n"
        "Use /add_from_passage to generate more cards from another passage."
    )

    # Reset session
    user_state_manager.reset_session(user_id)


@router.message()
async def text_message_handler(message: Message):
    """Handle text messages based on user state."""
    if not message.from_user or not message.text:
        return

    user_id = message.from_user.id
    session = user_state_manager.get_session(user_id)

    if session.state == UserState.WAITING_FOR_PASSAGE:
        # Generate cards from passage using OpenAI
        await message.answer("🤖 Analyzing your passage and generating optimal number of cards... Please wait.")

        try:
            request = CardGenerationRequest(
                passage=message.text, max_cards=openai_config.max_cards, difficulty="medium"
            )

            response = await openai_client.generate_cards_from_passage(request)

            if not response.cards:
                await message.answer("❌ Failed to generate cards from the passage. Please try with a different text.")
                user_state_manager.reset_session(user_id)
                return

            # Store generated cards and show them for review
            user_state_manager.update_session(
                user_id,
                passage=message.text,
                generated_cards=response.cards,
                cards_to_create=response.cards,
                state=UserState.WAITING_FOR_PASSAGE_DECK_SELECTION,
            )

            # Show generated cards
            cards_text = f"🤖 **Generated {len(response.cards)} cards:**\n\n"
            for i, card in enumerate(response.cards, 1):
                tags_str = f" (Tags: {', '.join(card.tags)})" if card.tags else ""
                cards_text += f"**Card {i}:**\n"
                cards_text += f"❓ **Front:** {card.front}\n"
                cards_text += f"💡 **Back:** {card.back}{tags_str}\n\n"

            cards_text += "📚 **Choose a deck to add these cards to:**"

            # Create inline keyboard for deck selection
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for deck in session.available_decks or []:
                keyboard.inline_keyboard.append(
                    [InlineKeyboardButton(text=deck["name"], callback_data=f"deck_{deck['id']}")]
                )

            await message.answer(cards_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error generating cards from passage for user {user_id}: {e}")
            await message.answer("❌ An error occurred while generating cards. Please try again.")
            user_state_manager.reset_session(user_id)

    elif session.state == UserState.WAITING_FOR_FRONT:
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

    elif session.state == UserState.WAITING_FOR_ENGLISH_WORD:
        # Generate English word card using OpenAI
        await message.answer("🤖 Generating comprehensive vocabulary card... Please wait.")

        try:
            request = EnglishWordRequest(word=message.text.strip())

            response: EnglishWordResponse = await openai_client.generate_english_word_card(request)

            if not response.word_card:
                await message.answer("❌ Failed to generate word card. Please try with a different word.")
                user_state_manager.reset_session(user_id)
                return

            # Store generated card and show it for review
            user_state_manager.update_session(
                user_id,
                english_word=message.text.strip(),
                generated_english_card=response.word_card,
                state=UserState.REVIEWING_ENGLISH_WORD_CARD,
            )

            # Show generated English word card
            card = response.word_card
            card_preview = "🔤 **English Word Card Preview:**\n\n"
            card_preview += f"**Word:** {card.word}\n\n"
            card_preview += f"**Definition:** {card.definition}\n\n"
            card_preview += f"**Part of Speech:** {card.part_of_speech}\n\n"
            card_preview += f"**Synonyms:** {card.synonyms}\n\n"
            card_preview += f"**Situations to Use It:** {card.situations_to_use}\n\n"
            card_preview += f"**Russian Translations:** {card.russian_translations}\n\n"
            card_preview += f"**Example Sentences:** {card.example_sentences}\n\n"
            card_preview += "📚 **Choose a deck to add this card to:**"

            # Create inline keyboard for deck selection
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for deck in session.available_decks or []:
                keyboard.inline_keyboard.append(
                    [InlineKeyboardButton(text=deck["name"], callback_data=f"english_deck_{deck['id']}")]
                )

            await message.answer(card_preview, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error generating English word card for user {user_id}: {e}")
            await message.answer("❌ An error occurred while generating the word card. Please try again.")
            user_state_manager.reset_session(user_id)

    elif session.state == UserState.IDLE:
        await message.answer("👋 Hi! Use /add_card to create a new Anki card, or /help to see all commands.")
