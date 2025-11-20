from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class CardGenerationInputDTO:
    word: str
    user_id: int
    chat_id: int


@dataclass(slots=True)
class CardGenerationOutputDTO:
    success: bool
    note_id: Optional[int] = None
    error: Optional[str] = None
