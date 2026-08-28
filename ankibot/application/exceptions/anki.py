from ankibot.application.exceptions.base import ApplicationError


class AnkiAuthenticationError(ApplicationError):
    message = "Failed to authenticate with AnkiWeb"


class AnkiInvalidUsernameError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the username"


class AnkiInvalidPasswordError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the password"


class AnkiSessionExpiredError(AnkiAuthenticationError):
    message = "AnkiWeb session is not established or has expired"


class AnkiCardCreationError(ApplicationError):
    message = "Failed to add the card to AnkiWeb"


class AnkiUnsupportedNotetypeError(AnkiCardCreationError):
    message = "AnkiWeb's current notetype doesn't have exactly two fields"
