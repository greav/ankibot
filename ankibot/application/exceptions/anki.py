from ankibot.application.exceptions.base import ApplicationError


class AnkiAuthenticationError(ApplicationError):
    message = "Failed to authenticate with AnkiWeb"


class AnkiInvalidUsernameError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the username"


class AnkiInvalidPasswordError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the password"


class AnkiSessionExpiredError(AnkiAuthenticationError):
    message = "AnkiWeb session is not established or has expired"


class AnkiDeckNotFoundError(ApplicationError):
    # Not under AnkiCardCreationError: it is raised both while selecting a deck and while adding a
    # card, and handlers must catch it before their generic ApplicationError branch.
    message = "The selected deck no longer exists in AnkiWeb"


class AnkiDeckListingError(ApplicationError):
    message = "Failed to read the deck list from AnkiWeb"


class AnkiCardCreationError(ApplicationError):
    message = "Failed to add the card to AnkiWeb"


class AnkiUnsupportedNotetypeError(AnkiCardCreationError):
    message = "The configured notetype doesn't have exactly two fields"


class AnkiTemplateTargetNotFoundError(AnkiCardCreationError):
    message = "The configured deck or notetype does not exist in AnkiWeb"


class SnippetCardsPartiallySavedError(AnkiCardCreationError):
    """AnkiWeb failed partway through a batch: ``saved`` of ``total`` cards made it into the deck.

    Raised only once at least one card is in — an all-or-nothing failure propagates as the error
    that caused it, so a session-expired first card still reads as "authenticate", not "partial".
    """

    def __init__(self, *, saved: int, total: int, deck_name: str) -> None:
        self.saved = saved
        self.total = total
        self.deck_name = deck_name
        super().__init__(f"Saved {saved} of {total} cards before AnkiWeb failed")
