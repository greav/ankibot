"""
Use case: Add Vocabulary Word.

Actor: Learner
Learner sends a word — or a screenshot of the text it appears in, picking the word out of it —
reviews the card an LLM filled in for it, asking for a redo with a note on what to change until it
reads right, and saves it to AnkiWeb.
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
from ankibot.application.add_vocabulary_word.suggest_words import (
    SuggestedWords,
    SuggestWords,
    SuggestWordsRequest,
    WordSuggester,
)

__all__ = [
    "CardFeedback",
    "CardGenerator",
    "GenerateCard",
    "GenerateCardRequest",
    "GeneratedCard",
    "SaveCard",
    "SaveCardRequest",
    "SaveCardResult",
    "SuggestWords",
    "SuggestWordsRequest",
    "SuggestedWords",
    "VocabularyCardGateway",
    "VocabularyTarget",
    "WordSuggester",
]
