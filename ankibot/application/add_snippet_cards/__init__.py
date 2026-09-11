"""
Use case: Add Snippet Cards.

Actor: Learner
Learner sends a passage from their reading (a text snippet or a screenshot), reviews the front/back
cards generated from it, keeps the ones worth learning — regenerating the rest until they are —
and saves them to the deck they picked.
"""

from ankibot.application.add_snippet_cards.generate_cards import (
    DraftCard,
    GenerateCards,
    GeneratedSnippetCards,
    GenerateSnippetCardsRequest,
    Snippet,
    SnippetCardsGenerator,
    SnippetImage,
)
from ankibot.application.add_snippet_cards.save_cards import SaveCards, SaveSnippetCardsRequest, SaveSnippetCardsResult

__all__ = [
    "DraftCard",
    "GenerateCards",
    "GenerateSnippetCardsRequest",
    "GeneratedSnippetCards",
    "SaveCards",
    "SaveSnippetCardsRequest",
    "SaveSnippetCardsResult",
    "Snippet",
    "SnippetCardsGenerator",
    "SnippetImage",
]
