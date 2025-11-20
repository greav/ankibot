from __future__ import annotations

from .base import ApplicationError


class CardGenerationError(ApplicationError):
    title = "Card generation failed"


class LLMError(CardGenerationError):
    title = "Unable to generate card with language model"


class AuthenticationError(CardGenerationError):
    title = "Authentication with AnkiWeb failed"


class AnkiAPIError(CardGenerationError):
    title = "Unexpected error while communicating with AnkiWeb"
