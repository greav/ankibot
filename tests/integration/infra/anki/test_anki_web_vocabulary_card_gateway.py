import httpx
import pytest

from ankibot.application.add_vocabulary_word import VocabularyTarget
from ankibot.application.exceptions.anki import (
    AnkiCardCreationError,
    AnkiSessionExpiredError,
    AnkiTemplateTargetNotFoundError,
)
from ankibot.domain.card_template import CardTemplate
from ankibot.infra.anki.svc import AnkiSvcClient, AnkiSvcClientConfig
from ankibot.infra.anki.vocabulary_card_gateway import AnkiWebVocabularyCardGateway, AnkiWebVocabularyCardGatewayConfig
from ankiweb.common_pb2 import DeckNameId, Notetype, NotetypeNameId, UInt32
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingResponse
from ankiweb.editor.get_notetype_fields_pb2 import GetNotetypeFieldsResponse
from tests.common.transport import Handler, client_for

DECK_ID = 42
DECK_NAME = "English Words V2"
OTHER_DECK_ID = 43
OTHER_DECK_NAME = "French"
NOTETYPE_ID = 7
NOTETYPE_NAME = "English Words V2"
OTHER_NOTETYPE_ID = 8
OTHER_NOTETYPE_NAME = "Basic"

# Deliberately out of ``ord`` order, to prove the gateway sorts by ``ord`` rather than list position.
NOTETYPE_FIELDS = [
    Notetype.Field(ord=UInt32(val=1), name="Meaning"),
    Notetype.Field(ord=UInt32(val=0), name="Word"),
    Notetype.Field(ord=UInt32(val=2), name="Example"),
]


def info_response() -> bytes:
    return GetInfoForAddingResponse(
        notetypes=[
            NotetypeNameId(id=NOTETYPE_ID, name=NOTETYPE_NAME),
            NotetypeNameId(id=OTHER_NOTETYPE_ID, name=OTHER_NOTETYPE_NAME),
        ],
        decks=[DeckNameId(id=DECK_ID, name=DECK_NAME), DeckNameId(id=OTHER_DECK_ID, name=OTHER_DECK_NAME)],
        current_deck_id=DECK_ID,
        current_notetype_id=NOTETYPE_ID,
    ).SerializeToString()


def fields_response(fields: list[Notetype.Field] = NOTETYPE_FIELDS) -> bytes:  # noqa: B006
    return GetNotetypeFieldsResponse(fields=fields).SerializeToString()


def build_handler(
    *,
    info_status_code: int = 200,
    info_content: bytes | None = None,
    fields_status_code: int = 200,
    fields_content: bytes | None = None,
    add_status_code: int = 200,
    add_content: bytes | None = None,
) -> Handler:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ankiuser.net"
        assert request.headers["Content-Type"] == "application/octet-stream"

        if request.url.path == "/svc/editor/get-info-for-adding":
            content = info_content if info_content is not None else info_response()
            return httpx.Response(info_status_code, content=content)

        if request.url.path == "/svc/editor/get-notetype-fields":
            content = fields_content if fields_content is not None else fields_response()
            return httpx.Response(fields_status_code, content=content)

        if request.url.path == "/svc/editor/add-or-update":
            content = add_content if add_content is not None else AddOrUpdateResponse().SerializeToString()
            return httpx.Response(add_status_code, content=content)

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


def make_gateway(svc_config: AnkiSvcClientConfig, client: httpx.AsyncClient) -> AnkiWebVocabularyCardGateway:
    config = AnkiWebVocabularyCardGatewayConfig(deck_name=DECK_NAME, notetype_name=NOTETYPE_NAME)
    return AnkiWebVocabularyCardGateway(config, AnkiSvcClient(svc_config, client))


async def test_gateway_can_resolve_the_configured_target(svc_config: AnkiSvcClientConfig) -> None:
    """target() issues both calls and builds the template ordered by ``ord``, not list position."""
    # Arrange / Act
    async with client_for(build_handler()) as client:
        gateway = make_gateway(svc_config, client)
        target = await gateway.target()

    # Assert
    assert target == VocabularyTarget(
        deck_id=DECK_ID,
        deck_name=DECK_NAME,
        notetype_id=NOTETYPE_ID,
        template=CardTemplate(name=NOTETYPE_NAME, fields=("Word", "Meaning", "Example")),
    )


async def test_gateway_cannot_resolve_an_unknown_deck_name(svc_config: AnkiSvcClientConfig) -> None:
    """A configured deck name absent from the account names the decks that do exist."""
    # Arrange
    config = AnkiWebVocabularyCardGatewayConfig(deck_name="Missing Deck", notetype_name=NOTETYPE_NAME)

    # Act / Assert
    async with client_for(build_handler()) as client:
        gateway = AnkiWebVocabularyCardGateway(config, AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiTemplateTargetNotFoundError) as excinfo:
            await gateway.target()

    assert DECK_NAME in str(excinfo.value)
    assert OTHER_DECK_NAME in str(excinfo.value)


async def test_gateway_cannot_resolve_an_unknown_notetype_name(svc_config: AnkiSvcClientConfig) -> None:
    """A configured notetype name absent from the account names the notetypes that do exist."""
    # Arrange
    config = AnkiWebVocabularyCardGatewayConfig(deck_name=DECK_NAME, notetype_name="Missing Notetype")

    # Act / Assert
    async with client_for(build_handler()) as client:
        gateway = AnkiWebVocabularyCardGateway(config, AnkiSvcClient(svc_config, client))
        with pytest.raises(AnkiTemplateTargetNotFoundError) as excinfo:
            await gateway.target()

    assert NOTETYPE_NAME in str(excinfo.value)
    assert OTHER_NOTETYPE_NAME in str(excinfo.value)


async def test_gateway_can_add_a_note_with_fields_in_template_order(svc_config: AnkiSvcClientConfig) -> None:
    """add_note posts the fields positionally, in the order the target's template lists them."""
    # Arrange
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return await build_handler()(request)

    target = VocabularyTarget(
        deck_id=DECK_ID,
        deck_name=DECK_NAME,
        notetype_id=NOTETYPE_ID,
        template=CardTemplate(name=NOTETYPE_NAME, fields=("Word", "Meaning", "Example")),
    )

    async with client_for(handler) as client:
        gateway = make_gateway(svc_config, client)

        # Act
        await gateway.add_note(target, ["hello", "a greeting", "Hello there!"])

    # Assert
    add_request = next(request for request in requests if request.url.path == "/svc/editor/add-or-update")
    parsed = AddOrUpdateRequest()
    parsed.ParseFromString(add_request.content)
    assert list(parsed.fields) == ["hello", "a greeting", "Hello there!"]
    assert parsed.add.notetype_id == NOTETYPE_ID
    assert parsed.add.deck_id == DECK_ID


async def test_gateway_can_render_line_breaks_as_html_for_ankiweb(svc_config: AnkiSvcClientConfig) -> None:
    """A multi-line value reaches AnkiWeb with ``<br>`` between the lines, since a field is HTML."""
    # Arrange
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return await build_handler()(request)

    target = VocabularyTarget(
        deck_id=DECK_ID,
        deck_name=DECK_NAME,
        notetype_id=NOTETYPE_ID,
        template=CardTemplate(name=NOTETYPE_NAME, fields=("Word", "Meaning", "Example")),
    )

    async with client_for(handler) as client:
        gateway = make_gateway(svc_config, client)

        # Act
        await gateway.add_note(target, ["wind", "1. moving air\n2. to twist", "A & B <3"])

    # Assert
    add_request = next(request for request in requests if request.url.path == "/svc/editor/add-or-update")
    parsed = AddOrUpdateRequest()
    parsed.ParseFromString(add_request.content)
    assert list(parsed.fields) == ["wind", "1. moving air<br>2. to twist", "A &amp; B &lt;3"]


async def test_gateway_cannot_resolve_a_target_on_an_expired_session(svc_config: AnkiSvcClientConfig) -> None:
    """A 403 from get-info-for-adding means the AnkiWeb session is not established or has expired."""
    # Arrange
    handler = build_handler(info_status_code=403)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = make_gateway(svc_config, client)
        with pytest.raises(AnkiSessionExpiredError):
            await gateway.target()


async def test_gateway_cannot_resolve_a_target_when_fields_are_served_as_html(svc_config: AnkiSvcClientConfig) -> None:
    """An HTML page served with 200 for get-notetype-fields fails loudly, not as a raw DecodeError."""
    # Arrange
    handler = build_handler(fields_content=b"<html><body>maintenance</body></html>")

    # Act / Assert
    async with client_for(handler) as client:
        gateway = make_gateway(svc_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.target()


async def test_gateway_cannot_reach_an_unreachable_ankiweb(svc_config: AnkiSvcClientConfig) -> None:
    """A transport failure becomes an application error, so the handler can still answer the user."""

    # Arrange
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    # Act / Assert
    async with client_for(handler) as client:
        gateway = make_gateway(svc_config, client)
        with pytest.raises(AnkiCardCreationError):
            await gateway.target()
