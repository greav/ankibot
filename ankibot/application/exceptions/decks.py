from ankibot.application.exceptions.base import ApplicationError


class NoDeckSelectedError(ApplicationError):
    """The user has not chosen a deck yet, so there is nowhere to put a card.

    Not under any AnkiWeb error: nothing was asked of AnkiWeb. The bot used to fall back to
    AnkiWeb's current deck here, which in practice was the hidden built-in one.
    """

    message = "No deck has been chosen yet"
