import httpx
import pytest

from ankibot.application.exceptions.anki import (
    AnkiDeckCreationError,
    AnkiDeckListingError,
    AnkiDeckRemovalError,
    AnkiSessionExpiredError,
)
from ankibot.application.manage_decks import Deck
from ankibot.infra.anki.deck_gateway import AnkiWebDeckGateway
from ankibot.infra.anki.svc import AnkiSvcClient, AnkiSvcClientConfig
from ankiweb.common_pb2 import DeckNameId
from ankiweb.decks.create_deck_pb2 import CreateDeckRequest, CreateDeckResponse
from ankiweb.decks.remove_deck_pb2 import RemoveDeckRequest, RemoveDeckResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingResponse
from tests.common.transport import Handler, client_for

DECKS = [DeckNameId(id=42, name="Spanish"), DeckNameId(id=43, name="French")]


def build_handler(*, status_code: int = 200, content: bytes | None = None) -> Handler:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ankiuser.net"
        assert request.url.path == "/svc/editor/get-info-for-adding"
        assert request.headers["Content-Type"] == "application/octet-stream"

        body = content if content is not None else GetInfoForAddingResponse(decks=DECKS).SerializeToString()
        return httpx.Response(status_code, content=body)

    return handler


async def test_gateway_can_list_the_accounts_decks(svc_config: AnkiSvcClientConfig) -> None:
    """Every deck the editor endpoint reports comes back, ids and names intact."""
    # Arrange
    async with client_for(build_handler()) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))

        # Act
        decks = await gateway.list_decks()

    # Assert
    assert decks == [Deck(id=42, name="Spanish"), Deck(id=43, name="French")]


async def test_gateway_can_list_an_empty_account(svc_config: AnkiSvcClientConfig) -> None:
    """An account with no decks yields an empty list, not an error."""
    # Arrange
    handler = build_handler(content=GetInfoForAddingResponse().SerializeToString())

    # Act
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        decks = await gateway.list_decks()

    # Assert
    assert decks == []


async def test_gateway_cannot_list_decks_on_an_expired_session(
    svc_config: AnkiSvcClientConfig,
) -> None:
    """A 403 means the AnkiWeb session is not established or has expired."""
    # Arrange
    handler = build_handler(status_code=403)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.list_decks()


async def test_gateway_cannot_list_decks_served_as_html(svc_config: AnkiSvcClientConfig) -> None:
    """An HTML page served with 200 surfaces as an application error, not a raw DecodeError."""
    # Arrange
    handler = build_handler(content=b"<html><body>maintenance</body></html>")

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiDeckListingError):
            await gateway.list_decks()


async def test_gateway_cannot_list_decks_from_an_unreachable_ankiweb(
    svc_config: AnkiSvcClientConfig,
) -> None:
    """A transport failure becomes an application error, so the handler can still answer the user."""

    # Arrange
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiDeckListingError):
            await gateway.list_decks()


def build_decks_handler(path: str, expected_body: bytes, response: bytes, *, status_code: int = 200) -> Handler:
    """A handler for one ``/svc/decks`` call, asserting it goes to ankiweb.net with the expected body."""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ankiweb.net"
        assert request.url.path == path
        assert request.headers["Content-Type"] == "application/octet-stream"
        assert request.content == expected_body
        return httpx.Response(status_code, content=response)

    return handler


async def test_gateway_can_create_a_deck(svc_config: AnkiSvcClientConfig) -> None:
    """Creating a deck posts its name to AnkiWeb's decks service on the main site, not the editor host."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/create-deck",
        CreateDeckRequest(name="Italian::Verbs").SerializeToString(),
        CreateDeckResponse().SerializeToString(),
    )

    # Act / Assert — nothing comes back to assert on beyond the request the handler checked.
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        await gateway.create_deck("Italian::Verbs")


async def test_gateway_cannot_create_a_deck_on_an_expired_session(svc_config: AnkiSvcClientConfig) -> None:
    """A 403 from the decks service means the ankiweb.net session is gone, the same as everywhere else."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/create-deck", CreateDeckRequest(name="Italian").SerializeToString(), b"", status_code=403
    )

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.create_deck("Italian")


async def test_gateway_cannot_create_a_deck_when_ankiweb_fails(svc_config: AnkiSvcClientConfig) -> None:
    """Any other HTTP failure is named as a deck-creation error, so the handler can pick its reply."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/create-deck", CreateDeckRequest(name="Italian").SerializeToString(), b"", status_code=500
    )

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiDeckCreationError):
            await gateway.create_deck("Italian")


async def test_gateway_can_remove_a_deck(svc_config: AnkiSvcClientConfig) -> None:
    """Deleting a deck posts its id to AnkiWeb's decks service on the main site."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/remove-deck",
        RemoveDeckRequest(deck_id=42).SerializeToString(),
        RemoveDeckResponse().SerializeToString(),
    )

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        await gateway.remove_deck(42)


async def test_gateway_cannot_remove_a_deck_on_an_expired_session(svc_config: AnkiSvcClientConfig) -> None:
    """A 403 while deleting means the session is gone; the deck is reported untouched, not deleted."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/remove-deck", RemoveDeckRequest(deck_id=42).SerializeToString(), b"", status_code=403
    )

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.remove_deck(42)


async def test_gateway_cannot_remove_a_deck_when_ankiweb_fails(svc_config: AnkiSvcClientConfig) -> None:
    """Any other HTTP failure is named as a deck-removal error, so the handler can pick its reply."""
    # Arrange
    handler = build_decks_handler(
        "/svc/decks/remove-deck", RemoveDeckRequest(deck_id=42).SerializeToString(), b"", status_code=500
    )

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebDeckGateway(AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiDeckRemovalError):
            await gateway.remove_deck(42)
