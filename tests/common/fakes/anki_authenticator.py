"""In-memory implementation of the AnkiAuthenticator port."""

from typing import override

from ankibot.application.anki_authentication.authenticate_anki import AnkiAuthenticator


class FakeAnkiAuthenticator(AnkiAuthenticator):
    """Authenticates without leaving the process, or raises ``error`` instead when one is set.

    ``error`` stays writable so a test sharing one dispatcher can steer the run it is about to make.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    @override
    async def authenticate(self) -> None:
        """Raise the configured error, or succeed silently when there is none."""
        if self.error is not None:
            raise self.error
