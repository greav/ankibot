from ankibot.application.exceptions.base import ApplicationError


class AnkiAuthenticationError(ApplicationError):
    message = "Failed to authenticate with AnkiWeb"


class AnkiInvalidUsernameError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the username"


class AnkiInvalidPasswordError(AnkiAuthenticationError):
    message = "AnkiWeb rejected the password"
