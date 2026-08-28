import logging

import httpx
import pytest

from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiSessionExpiredError
from ankibot.application.manage_cards.create_card import AddTarget, CreateCardRequest
from ankibot.infra.anki.card_gateway import AnkiWebCardGateway, AnkiWebCardGatewayConfig
from ankiweb.common_pb2 import DeckNameId, Notetype, NotetypeNameId, UInt32
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingResponse
from tests.common.transport import Handler, client_for

DECK_ID = 42
NOTETYPE_ID = 7
DECK_NAME = "Spanish"
BASIC_FIELDS = [Notetype.Field(ord=UInt32(val=0), name="Front"), Notetype.Field(ord=UInt32(val=1), name="Back")]


def info_response(*, current_deck_id: int = DECK_ID, fields: list[Notetype.Field] = BASIC_FIELDS) -> bytes:
    return GetInfoForAddingResponse(
        notetypes=[NotetypeNameId(id=NOTETYPE_ID, name="Basic")],
        decks=[DeckNameId(id=DECK_ID, name=DECK_NAME)],
        current_deck_id=current_deck_id,
        current_notetype_id=NOTETYPE_ID,
        fields=fields,
    ).SerializeToString()


def build_handler(
    *,
    info_status_code: int = 200,
    info_content: bytes | None = None,
    add_status_code: int = 200,
    add_content: bytes | None = None,
) -> Handler:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ankiuser.net"
        assert request.headers["Content-Type"] == "application/octet-stream"

        if request.url.path == "/svc/editor/get-info-for-adding":
            content = info_content if info_content is not None else info_response()
            return httpx.Response(info_status_code, content=content)

        if request.url.path == "/svc/editor/add-or-update":
            content = add_content if add_content is not None else AddOrUpdateResponse().SerializeToString()
            return httpx.Response(add_status_code, content=content)

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


async def test_gateway_can_read_the_current_add_target(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """current_add_target resolves the deck name matching AnkiWeb's current_deck_id."""
    # Arrange
    async with client_for(build_handler()) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)

        # Act
        target = await gateway.current_add_target()

    # Assert
    assert target == AddTarget(deck_id=DECK_ID, notetype_id=NOTETYPE_ID, deck_name=DECK_NAME, field_count=2)


async def test_gateway_can_read_a_notetypes_field_count(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """field_count reflects the current notetype's actual field list, not a hardcoded assumption."""
    # Arrange
    fields = [*BASIC_FIELDS, Notetype.Field(ord=UInt32(val=2), name="Extra")]
    handler = build_handler(info_content=info_response(fields=fields))

    # Act
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        target = await gateway.current_add_target()

    # Assert
    assert target.field_count == 3


async def test_gateway_can_add_a_card_to_the_current_target(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """add_card posts the note with the ids current_add_target reported, to the ankiuser host."""
    # Arrange
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/svc/editor/get-info-for-adding":
            return httpx.Response(200, content=info_response())
        return httpx.Response(200, content=AddOrUpdateResponse().SerializeToString())

    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        target = await gateway.current_add_target()

        # Act
        await gateway.add_card(target, CreateCardRequest(front="front", back="back"))

    # Assert
    add_request = next(request for request in requests if request.url.path == "/svc/editor/add-or-update")
    assert add_request.url.host == "ankiuser.net"
    assert add_request.headers["Content-Type"] == "application/octet-stream"
    parsed = AddOrUpdateRequest()
    parsed.ParseFromString(add_request.content)
    assert list(parsed.fields) == ["front", "back"]
    assert parsed.add.notetype_id == NOTETYPE_ID
    assert parsed.add.deck_id == DECK_ID


async def test_gateway_cannot_resolve_an_unknown_current_deck_id(
    card_gateway_config: AnkiWebCardGatewayConfig,
) -> None:
    """An AnkiWeb current_deck_id matching no deck in the list fails loudly instead of guessing a name."""
    # Arrange
    handler = build_handler(info_content=info_response(current_deck_id=999))

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.current_add_target()


async def test_gateway_cannot_read_the_add_target_on_an_expired_session(
    card_gateway_config: AnkiWebCardGatewayConfig,
) -> None:
    """A 403 from get-info-for-adding means the AnkiWeb session is not established or has expired."""
    # Arrange
    handler = build_handler(info_status_code=403)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.current_add_target()


async def test_gateway_cannot_add_a_card_on_an_expired_session(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """A 403 from add-or-update means the AnkiWeb session is not established or has expired."""
    # Arrange
    handler = build_handler(add_status_code=403)
    target = AddTarget(deck_id=DECK_ID, notetype_id=NOTETYPE_ID, deck_name=DECK_NAME, field_count=2)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.add_card(target, CreateCardRequest(front="front", back="back"))


async def test_gateway_cannot_read_the_add_target_on_an_http_error(
    card_gateway_config: AnkiWebCardGatewayConfig,
) -> None:
    """A non-200, non-403 response from AnkiWeb fails instead of being parsed as a valid response."""
    # Arrange
    handler = build_handler(info_status_code=500)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.current_add_target()


async def test_gateway_cannot_reach_an_unreachable_ankiweb(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """A transport failure becomes an application error, so the handler can still answer the user."""

    # Arrange
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.current_add_target()


async def test_gateway_cannot_read_an_add_target_served_as_html(card_gateway_config: AnkiWebCardGatewayConfig) -> None:
    """An HTML page served with 200 surfaces as AnkiCardCreationError, not a raw protobuf DecodeError."""
    # Arrange
    handler = build_handler(info_content=b"<html><body>maintenance</body></html>")

    # Act / Assert
    async with client_for(handler) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.current_add_target()


async def test_gateway_cannot_leak_card_text_into_the_logs(
    card_gateway_config: AnkiWebCardGatewayConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Card contents never reach the log stream, even at DEBUG level."""
    # Arrange
    front, back = "distinctive-front-s3cr3t", "distinctive-back-s3cr3t"
    target = AddTarget(deck_id=DECK_ID, notetype_id=NOTETYPE_ID, deck_name=DECK_NAME, field_count=2)

    async with client_for(build_handler()) as client:
        gateway = AnkiWebCardGateway(card_gateway_config, client)

        # Act
        with caplog.at_level(logging.DEBUG):
            await gateway.add_card(target, CreateCardRequest(front=front, back=back))

    # Assert
    assert front not in caplog.text
    assert back not in caplog.text
