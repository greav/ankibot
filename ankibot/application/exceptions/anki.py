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
    message = "AnkiWeb's current notetype doesn't have exactly two fields"
