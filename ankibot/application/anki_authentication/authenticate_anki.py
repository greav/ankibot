from abc import abstractmethod
from typing import Protocol


class AnkiAuthenticator(Protocol):
    """Establishes an authenticated AnkiWeb session for subsequent requests."""

    @abstractmethod
    async def authenticate(self) -> None:
        """Authenticate against AnkiWeb, raising an ``AnkiAuthenticationError`` subclass on failure."""
        raise NotImplementedError


class AuthenticateAnki:
    def __init__(self, authenticator: AnkiAuthenticator) -> None:
        self._authenticator = authenticator

    async def execute(self) -> None:
        await self._authenticator.authenticate()
