"""
Use case: Add Vocabulary Word.

Actor: Learner
Learner sends a word, reviews the card an LLM filled in for it — asking for a redo, with a note on
what to change, until it reads right — and saves it to AnkiWeb.
"""

from ankibot.application.add_vocabulary_word.generate_card import (
    CardFeedback,
    CardGenerator,
    GenerateCard,
    GenerateCardRequest,
    GeneratedCard,
)
from ankibot.application.add_vocabulary_word.ports import VocabularyCardGateway, VocabularyTarget
from ankibot.application.add_vocabulary_word.save_card import SaveCard, SaveCardRequest, SaveCardResult

__all__ = [
    "CardFeedback",
    "CardGenerator",
    "GenerateCard",
    "GenerateCardRequest",
    "GeneratedCard",
    "SaveCard",
    "SaveCardRequest",
    "SaveCardResult",
    "VocabularyCardGateway",
    "VocabularyTarget",
]
