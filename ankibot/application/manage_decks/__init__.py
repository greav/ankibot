"""
Use case: Manage Decks.

Actor: Learner
Learner browses the decks of the AnkiWeb account, picks the one new cards go to, and creates or
deletes decks without leaving Telegram.
"""

from ankibot.application.manage_decks.create_deck import CreateDeck, CreateDeckRequest, CreateDeckResult
from ankibot.application.manage_decks.list_decks import ListDecks, ListDecksRequest, ListDecksResult
from ankibot.application.manage_decks.ports import Deck
from ankibot.application.manage_decks.remove_deck import RemoveDeck, RemoveDeckRequest, RemoveDeckResult
from ankibot.application.manage_decks.select_deck import SelectDeck, SelectDeckRequest, SelectDeckResult

__all__ = [
    "CreateDeck",
    "CreateDeckRequest",
    "CreateDeckResult",
    "Deck",
    "ListDecks",
    "ListDecksRequest",
    "ListDecksResult",
    "RemoveDeck",
    "RemoveDeckRequest",
    "RemoveDeckResult",
    "SelectDeck",
    "SelectDeckRequest",
    "SelectDeckResult",
]
