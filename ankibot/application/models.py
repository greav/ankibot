from typing import List

from pydantic import BaseModel, Field


class AnkiCard(BaseModel):
    """Represents a single Anki card generated from a passage."""

    front: str = Field(description="The question or prompt for the front of the card")
    back: str = Field(description="The answer or explanation for the back of the card")
    tags: List[str] = Field(default_factory=list, description="Relevant tags for the card")


class CardGenerationResponse(BaseModel):
    """Response model for generating multiple Anki cards from a passage."""

    cards: List[AnkiCard] = Field(description="List of generated Anki cards")
    summary: str = Field(description="Brief summary of the passage")


class CardGenerationRequest(BaseModel):
    """Request model for card generation."""

    passage: str = Field(description="The text passage to generate cards from")
    max_cards: int = Field(default=10, ge=1, le=15, description="Maximum number of cards to generate (1-15)")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    focus_areas: List[str] = Field(
        default_factory=list,
        description="Specific areas to focus on (e.g., 'key concepts', 'definitions', 'examples')",
    )


class EnglishWordCard(BaseModel):
    """Represents an English word card with detailed context information."""

    word: str = Field(description="The English word or phrase")
    definition: str = Field(
        description="A concise explanation of the word, avoiding the word itself, "
        "noting its commonality (common/uncommon) and typical usage context"
    )
    part_of_speech: str = Field(description="The grammatical part of speech (noun, verb, adjective, etc.)")
    synonyms: str = Field(description="A few simpler words or phrases with similar meanings, comma-delimited")
    situations_to_use: str = Field(
        description="Bullet points explaining scenarios where the word is appropriately used"
    )
    russian_translations: str = Field(description="Russian translations, comma-delimited")
    example_sentences: str = Field(
        description="Five short, easy-to-understand sentences that illustrate the word's meaning, "
        "each with a brief meaning in parentheses"
    )


class EnglishWordResponse(BaseModel):
    """Response model for English word card generation."""

    word_card: EnglishWordCard = Field(description="Generated English word card with context")


class EnglishWordRequest(BaseModel):
    """Request model for English word card generation."""

    word: str = Field(description="The English word or phrase to generate a card for")
