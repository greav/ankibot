"""In-memory implementation of the CardGateway port."""

from typing import override

from ankibot.application.manage_cards.create_card import AddTarget, CardGateway, CreateCardRequest


class FakeCardGateway(CardGateway):
    """Adds cards without leaving the process, or raises ``error`` instead when one is set.

    ``target``/``error`` stay writable so a test sharing one dispatcher can steer the run it is
    about to make.
    """

    def __init__(self, target: AddTarget, error: Exception | None = None) -> None:
        self.target = target
        self.error = error

    @override
    async def current_add_target(self) -> AddTarget:
        """Raise the configured error, or return ``target`` when there is none."""
        if self.error is not None:
            raise self.error
        return self.target

    @override
    async def add_card(self, target: AddTarget, request: CreateCardRequest) -> None:
        """Raise the configured error, or succeed silently when there is none."""
        if self.error is not None:
            raise self.error
