import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import override

from ankibot.application.add_vocabulary_word.ports import VocabularyCardGateway, VocabularyTarget
from ankibot.application.exceptions.anki import AnkiCardCreationError, AnkiTemplateTargetNotFoundError
from ankibot.domain.card_template import CardTemplate
from ankibot.infra.anki.svc import AnkiSvcClient
from ankiweb.editor.add_or_update_pb2 import AddOrUpdateRequest, AddOrUpdateResponse
from ankiweb.editor.get_info_for_adding_pb2 import GetInfoForAddingRequest, GetInfoForAddingResponse
from ankiweb.editor.get_notetype_fields_pb2 import GetNotetypeFieldsRequest, GetNotetypeFieldsResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnkiWebVocabularyCardGatewayConfig:
    deck_name: str
    notetype_name: str


class AnkiWebVocabularyCardGateway(VocabularyCardGateway):
    """Adds vocabulary notes through AnkiWeb's editor endpoints, targeting a configured deck/notetype.

    See docs/ankiweb-api.md for the `editor/get-info-for-adding` → `editor/get-notetype-fields` →
    `editor/add-or-update` chain.
    """

    def __init__(self, config: AnkiWebVocabularyCardGatewayConfig, svc: AnkiSvcClient) -> None:
        self._config = config
        self._svc = svc

    @override
    async def target(self) -> VocabularyTarget:
        info = await self._svc.post(
            "/svc/editor/get-info-for-adding",
            GetInfoForAddingRequest(),
            GetInfoForAddingResponse(),
            error=AnkiCardCreationError,
        )

        deck_id = next((deck.id for deck in info.decks if deck.name == self._config.deck_name), None)
        if deck_id is None:
            available = ", ".join(deck.name for deck in info.decks)
            raise AnkiTemplateTargetNotFoundError(
                f"Deck '{self._config.deck_name}' not found in AnkiWeb. Available decks: {available}"
            )

        notetype_id = next(
            (notetype.id for notetype in info.notetypes if notetype.name == self._config.notetype_name), None
        )
        if notetype_id is None:
            available = ", ".join(notetype.name for notetype in info.notetypes)
            raise AnkiTemplateTargetNotFoundError(
                f"Notetype '{self._config.notetype_name}' not found in AnkiWeb. Available notetypes: {available}"
            )

        fields_response = await self._svc.post(
            "/svc/editor/get-notetype-fields",
            GetNotetypeFieldsRequest(notetype_id=notetype_id),
            GetNotetypeFieldsResponse(),
            error=AnkiCardCreationError,
        )
        ordered_fields = sorted(fields_response.fields, key=lambda field: field.ord.val)

        return VocabularyTarget(
            deck_id=deck_id,
            deck_name=self._config.deck_name,
            notetype_id=notetype_id,
            template=CardTemplate(
                name=self._config.notetype_name,
                fields=tuple(field.name for field in ordered_fields),
            ),
        )

    @override
    async def add_note(self, target: VocabularyTarget, fields: Sequence[str]) -> None:
        add_request = AddOrUpdateRequest(
            fields=list(fields),
            tags="",
            add=AddOrUpdateRequest.AddMode(notetype_id=target.notetype_id, deck_id=target.deck_id),
        )
        await self._svc.post(
            "/svc/editor/add-or-update",
            add_request,
            AddOrUpdateResponse(),
            error=AnkiCardCreationError,
        )

        logger.info("Added vocabulary card to AnkiWeb deck %s", target.deck_id, extra={"deck_id": target.deck_id})
