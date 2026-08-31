from ankibot.application.exceptions.base import ApplicationError


class CardGenerationError(ApplicationError):
    message = "Failed to generate a card"


class CardGenerationUnavailableError(CardGenerationError):
    message = "The card generator is unavailable"


class CardGenerationIncompleteError(CardGenerationError):
    message = "The generator did not fill every field"


class CardGenerationEmptyError(CardGenerationError):
    message = "The generator found nothing to make cards from"
