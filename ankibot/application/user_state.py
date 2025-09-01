from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .models import AnkiCard, EnglishWordCard


class UserState(Enum):
    """User interaction states for card creation flow."""

    IDLE = "idle"
    WAITING_FOR_FRONT = "waiting_for_front"
    WAITING_FOR_BACK = "waiting_for_back"
    WAITING_FOR_TAGS = "waiting_for_tags"
    WAITING_FOR_DECK_SELECTION = "waiting_for_deck_selection"
    WAITING_FOR_PASSAGE = "waiting_for_passage"
    WAITING_FOR_PASSAGE_DECK_SELECTION = "waiting_for_passage_deck_selection"
    REVIEWING_GENERATED_CARDS = "reviewing_generated_cards"
    WAITING_FOR_ENGLISH_WORD = "waiting_for_english_word"
    REVIEWING_ENGLISH_WORD_CARD = "reviewing_english_word_card"


@dataclass
class CardCreationSession:
    """Session data for card creation process."""

    state: UserState
    front: Optional[str] = None
    back: Optional[str] = None
    tags: Optional[str] = None
    deck_id: Optional[int] = None
    notetype_id: Optional[int] = None
    available_decks: Optional[list[dict[str, Any]]] = None
    available_notetypes: Optional[list[dict[str, Any]]] = None
    # Passage-based card generation fields
    passage: Optional[str] = None
    generated_cards: Optional[list[AnkiCard]] = None
    current_card_index: int = 0
    cards_to_create: Optional[list[AnkiCard]] = None
    # English word card generation fields
    english_word: Optional[str] = None
    generated_english_card: Optional[EnglishWordCard] = None


class UserStateManager:
    """Manages user states for card creation sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[int, CardCreationSession] = {}

    def get_session(self, user_id: int) -> CardCreationSession:
        """Get or create a session for the user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = CardCreationSession(state=UserState.IDLE)
        return self._sessions[user_id]

    def reset_session(self, user_id: int) -> None:
        """Reset user's session to initial state."""
        self._sessions[user_id] = CardCreationSession(state=UserState.IDLE)

    def update_session(self, user_id: int, **kwargs) -> None:
        """Update session parameters."""
        session = self.get_session(user_id)
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

    def clear_session(self, user_id: int) -> None:
        """Remove user's session completely."""
        self._sessions.pop(user_id, None)
