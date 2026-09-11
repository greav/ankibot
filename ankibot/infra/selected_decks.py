"""The file behind every user's deck choice.

The whole map is a few bytes, so it is read once at construction and rewritten in full on every
change: an atomic replace of one small file is simpler and safer than updating it in place, and
a crash mid-write leaves the previous file intact rather than half a new one. Reads never touch
the disk; the dict loaded at start is the read path and every ``set`` keeps it current.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import override

from ankibot.application.common.selected_deck_store import SelectedDeckStore


@dataclass(frozen=True, kw_only=True)
class JsonFileSelectedDeckStoreConfig:
    path: str
    """The JSON file holding ``{"<user_id>": <deck_id>}``; its directory is created on first write."""


class JsonFileSelectedDeckStore(SelectedDeckStore):
    """Keeps each user's deck choice in a JSON file, so it survives a restart.

    A missing file is an empty store. A file that is not a JSON object of integer ids raises
    ``ValueError`` at construction: ``warm_up`` resolves this port before polling starts, so a
    corrupt file refuses to start the bot instead of silently sending cards to the wrong deck.
    """

    def __init__(self, config: JsonFileSelectedDeckStoreConfig) -> None:
        self._path = Path(config.path)
        self._decks = self._load()
        self._lock = asyncio.Lock()

    def _load(self) -> dict[int, int]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                msg = "expected a JSON object"
                raise TypeError(msg)
            return {int(user_id): int(deck_id) for user_id, deck_id in raw.items()}
        except (ValueError, TypeError) as error:
            msg = f"Selected decks file {self._path} is not a JSON object of user id to deck id: {error}"
            raise ValueError(msg) from error

    @override
    async def get(self, user_id: int) -> int | None:
        return self._decks.get(user_id)

    @override
    async def set(self, user_id: int, deck_id: int) -> None:
        async with self._lock:
            self._decks[user_id] = deck_id
            self._write()

    def _write(self) -> None:
        """Rewrite the file atomically: the new content lands under a temporary name, then replaces the old."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(json.dumps({str(user_id): deck_id for user_id, deck_id in self._decks.items()}))
        os.replace(temporary, self._path)
