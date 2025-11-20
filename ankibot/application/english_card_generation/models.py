from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class GeneratedCard:
    word: str
    definition: str
    part_of_speech: str
    synonyms: List[str] = field(default_factory=list)
    russian_translations: List[str] = field(default_factory=list)
    example_sentences: List[str] = field(default_factory=list)


@dataclass(slots=True)
class CardTemplate:
    """Configuration describing how to build Anki fields and prompts."""

    prompt: str
    field_mapping: Dict[str, str]
    tags: List[str] = field(default_factory=list)
    list_delimiter: str = "; "


@dataclass(slots=True)
class EditorInfo:
    """Subset of data returned by Anki editor info endpoint."""

    notetype_id: int
    field_order: List[str]


@dataclass(slots=True)
class AddNotePayload:
    deck_id: int
    notetype_id: int
    fields: List[str]
    tags: List[str] = field(default_factory=list)
