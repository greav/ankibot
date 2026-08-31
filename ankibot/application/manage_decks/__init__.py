"""
Use case: Manage Decks.

Actor: Learner
Learner browses the decks of the AnkiWeb account and picks the one new cards go to.
"""

from ankibot.application.manage_decks.list_decks import ListDecks, ListDecksRequest, ListDecksResult
from ankibot.application.manage_decks.ports import Deck
from ankibot.application.manage_decks.select_deck import SelectDeck, SelectDeckRequest, SelectDeckResult

__all__ = [
    "Deck",
    "ListDecks",
    "ListDecksRequest",
    "ListDecksResult",
    "SelectDeck",
    "SelectDeckRequest",
    "SelectDeckResult",
]
