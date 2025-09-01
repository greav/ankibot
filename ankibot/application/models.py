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
