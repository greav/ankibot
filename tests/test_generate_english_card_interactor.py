import asyncio

import pytest

from ankibot.application.english_card_generation import (
    CardGenerationInputDTO,
    CardTemplate,
    GenerateEnglishCardInteractor,
)
from ankibot.application.english_card_generation.models import EditorInfo, GeneratedCard
from ankibot.application.exceptions.card_generation import LLMError


class StubCardGenerator:
    def __init__(self, card: GeneratedCard | None = None, raises: Exception | None = None) -> None:
        self._card = card
        self._raises = raises

    async def generate_card(self, word: str, template: CardTemplate) -> GeneratedCard:
        if self._raises:
            raise self._raises
        assert word
        assert template
        return self._card or GeneratedCard(
            word=word,
            definition="definition",
            part_of_speech="noun",
        )


class StubGateway:
    def __init__(self, note_id: int = 123) -> None:
        self.note_id = note_id
        self.recorded_payload = None

    async def get_default_deck_id(self) -> int:
        return 42

    async def get_editor_info(self) -> EditorInfo:
        return EditorInfo(notetype_id=7, field_order=["Word", "Definition", "Synonyms"])

    async def add_note(self, payload):
        self.recorded_payload = payload
        return self.note_id


@pytest.mark.parametrize("synonyms", [["ally"], ["ally", "supporter"]])
def test_interactor_saves_note(synonyms):
    async def runner() -> None:
        generator = StubCardGenerator(
            GeneratedCard(
                word="friend",
                definition="a person with whom one has a bond",
                part_of_speech="noun",
                synonyms=synonyms,
            )
        )
        gateway = StubGateway()
        template = CardTemplate(
            prompt="",
            field_mapping={
                "Word": "word",
                "Definition": "definition",
                "Synonyms": "synonyms",
            },
        )

        interactor = GenerateEnglishCardInteractor(generator, gateway, template)
        result = await interactor(CardGenerationInputDTO(word="friend", user_id=1, chat_id=1))

        assert result.success is True
        assert result.note_id == gateway.note_id
        assert gateway.recorded_payload is not None
        assert gateway.recorded_payload.fields[0] == "friend"
        assert gateway.recorded_payload.fields[2].startswith("ally")

    asyncio.run(runner())


def test_interactor_wraps_llm_errors():
    async def runner() -> None:
        generator = StubCardGenerator(raises=ValueError("boom"))
        gateway = StubGateway()
        template = CardTemplate(prompt="", field_mapping={})
        interactor = GenerateEnglishCardInteractor(generator, gateway, template)

        with pytest.raises(LLMError):
            await interactor(CardGenerationInputDTO(word="friend", user_id=1, chat_id=1))

    asyncio.run(runner())
