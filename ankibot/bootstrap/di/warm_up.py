"""Build every APP-scoped dependency before the bot starts accepting updates.

The container is lazy, so an adapter that cannot be constructed at all is built on whichever update
first needs it, and the errors router answers with its generic reply — an empty ``OPENAI_API_KEY``
reaches the user as "Something went wrong" on the first word they send, hours after a clean start.
Resolving the adapters here turns that into a refusal to start, with the adapter's own error.

``STRICT_VALIDATION`` does not cover this: it checks that the graph is complete, not that the
objects in it can be built.
"""

from typing import Any

from dishka import AsyncContainer

from ankibot.application.add_snippet_cards import SnippetCardsGenerator
from ankibot.application.add_vocabulary_word import CardGenerator, VocabularyCardGateway
from ankibot.application.anki_authentication.authenticate_anki import AnkiAuthenticator
from ankibot.application.common.card_gateway import CardGateway
from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.manage_decks.ports import DeckGateway

# Every port the bot talks through — the same set ``tests/common/fakes/ports.py`` substitutes.
# Resolving them pulls in the HTTP and SDK clients behind them. Interactors are left out on purpose:
# they are REQUEST-scoped and rebuilt per update, so building one now proves nothing about the next.
# The annotation is `Any` because these are `Protocol`s, which mypy refuses where `type[T]` is asked.
_PORTS: tuple[Any, ...] = (
    AnkiAuthenticator,
    CardGateway,
    DeckGateway,
    SelectedDeckStore,
    VocabularyCardGateway,
    CardGenerator,
    SnippetCardsGenerator,
)


async def warm_up(container: AsyncContainer) -> None:
    """Resolve every port, so a misconfigured adapter fails here rather than mid-conversation."""
    for port in _PORTS:
        await container.get(port)
