from ankibot.application.exceptions.base import ApplicationError


class NoDeckSelectedError(ApplicationError):
    """The user has not chosen a deck yet, so there is nowhere to put a card.

    Not under any AnkiWeb error: nothing was asked of AnkiWeb. The bot used to fall back to
    AnkiWeb's current deck here, which in practice was the hidden built-in one.
    """

    message = "No deck has been chosen yet"


class BlankDeckNameError(ApplicationError):
    """The name offered for a new deck has nothing in it once Anki's normalization runs."""

    message = "A deck name cannot be blank"


class DeckAlreadyExistsError(ApplicationError):
    """A deck with that name is already in the account; Anki names are unique ignoring case."""

    def __init__(self, deck_name: str) -> None:
        self.deck_name = deck_name
        super().__init__(f"A deck named {deck_name} already exists")
