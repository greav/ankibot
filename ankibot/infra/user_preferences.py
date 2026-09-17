"""The file behind every user's choices: the deck cards go to and the model that writes them.

The whole map is a few bytes, so it is read once at construction and rewritten in full on every
change: an atomic replace of one small file is simpler and safer than updating it in place, and
a crash mid-write leaves the previous file intact rather than half a new one. Reads never touch
the disk; the dict loaded at start is the read path and every ``set_*`` keeps it current.

One adapter serves both ``SelectedDeckStore`` and ``SelectedModelStore``: the choices belong to
the same user and live in the same file, and a class per port would race each other for it.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import override

from ankibot.application.common.selected_deck_store import SelectedDeckStore
from ankibot.application.common.selected_model_store import SelectedModelStore

_DECK_KEY = "deck_id"
_MODEL_KEY = "model"


@dataclass(frozen=True, kw_only=True)
class JsonFileUserPreferencesStoreConfig:
    path: str
    """The JSON file holding ``{"<user_id>": {"deck_id": <int>, "model": "<id>"}}``, both fields
    optional; its directory is created on first write."""


@dataclass(frozen=True, kw_only=True)
class _Preferences:
    deck_id: int | None = None
    model: str | None = None


class JsonFileUserPreferencesStore(SelectedDeckStore, SelectedModelStore):
    """Keeps each user's deck and model choice in a JSON file, so they survive a restart.

    A missing file is an empty store. A file that is not a JSON object of per-user objects raises
    ``ValueError`` at construction: ``warm_up`` resolves these ports before polling starts, so a
    corrupt file refuses to start the bot instead of silently sending cards to the wrong deck.
    """

    def __init__(self, config: JsonFileUserPreferencesStoreConfig) -> None:
        self._path = Path(config.path)
        self._preferences = self._load()
        self._lock = asyncio.Lock()

    def _load(self) -> dict[int, _Preferences]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                msg = "expected a JSON object"
                raise TypeError(msg)
            return {int(user_id): _parse_preferences(entry) for user_id, entry in raw.items()}
        except (ValueError, TypeError) as error:
            msg = f"User preferences file {self._path} is not a JSON object of user id to preferences: {error}"
            raise ValueError(msg) from error

    @override
    async def get_deck(self, user_id: int) -> int | None:
        preferences = self._preferences.get(user_id)
        return preferences.deck_id if preferences is not None else None

    @override
    async def set_deck(self, user_id: int, deck_id: int) -> None:
        async with self._lock:
            current = self._preferences.get(user_id, _Preferences())
            self._preferences[user_id] = _Preferences(deck_id=deck_id, model=current.model)
            self._write()

    @override
    async def clear_deck(self, user_id: int) -> None:
        async with self._lock:
            current = self._preferences.get(user_id)
            if current is None or current.deck_id is None:
                return
            self._preferences[user_id] = _Preferences(deck_id=None, model=current.model)
            self._write()

    @override
    async def get_model(self, user_id: int) -> str | None:
        preferences = self._preferences.get(user_id)
        return preferences.model if preferences is not None else None

    @override
    async def set_model(self, user_id: int, model_id: str) -> None:
        async with self._lock:
            current = self._preferences.get(user_id, _Preferences())
            self._preferences[user_id] = _Preferences(deck_id=current.deck_id, model=model_id)
            self._write()

    def _write(self) -> None:
        """Rewrite the file atomically: the new content lands under a temporary name, then replaces the old."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        content = {str(user_id): _dump_preferences(preferences) for user_id, preferences in self._preferences.items()}
        temporary.write_text(json.dumps(content))
        os.replace(temporary, self._path)


def _parse_preferences(entry: object) -> _Preferences:
    if not isinstance(entry, dict):
        msg = "expected a JSON object per user"
        raise TypeError(msg)
    deck_id = entry.get(_DECK_KEY)
    model = entry.get(_MODEL_KEY)
    if model is not None and not isinstance(model, str):
        msg = f"expected {_MODEL_KEY!r} to be a string"
        raise TypeError(msg)
    return _Preferences(deck_id=int(deck_id) if deck_id is not None else None, model=model)


def _dump_preferences(preferences: _Preferences) -> dict[str, int | str]:
    entry: dict[str, int | str] = {}
    if preferences.deck_id is not None:
        entry[_DECK_KEY] = preferences.deck_id
    if preferences.model is not None:
        entry[_MODEL_KEY] = preferences.model
    return entry
