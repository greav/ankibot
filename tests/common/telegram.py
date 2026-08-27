"""Test doubles for the aiogram objects handlers work with.

The double sits at the session — the last layer before the network — so ``Bot``, ``Message`` and
the API method objects handlers build are all real. Assertions therefore see exactly what would
have been sent to Telegram, fields and all.

It is a recorder, not a Telegram simulator: it proves what we send, never what the API would answer.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, cast, override

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Message, User

TEST_BOT_TOKEN = "42:TEST"
TEST_CHAT_ID = 1
TEST_USER_ID = 2


UNREAD_RESULT_MESSAGE = (
    "A handler read back the result of a Telegram call, which RecordingSession cannot answer. "
    "Queue a real aiogram object for that method instead of inventing a reply "
    '(AGENTS.md, "The Telegram boundary").'
)


class UnreadResult:
    """Stands in for a result no covered handler reads back, and refuses to be read.

    Answering with a bare ``{}`` would be a fabricated API reply. Harmless while every handler
    discards its result, but ``{}`` is *falsy*: the day a handler branches on what
    ``delete_message`` or ``edit_message_text`` (``Message | bool``) returned, it would silently
    take the failure branch and the test would pass, asserting behaviour Telegram never produces.
    Failing here turns that into a message naming the rule.
    """

    def __getattr__(self, name: str) -> object:
        raise AssertionError(UNREAD_RESULT_MESSAGE)

    def __bool__(self) -> bool:
        raise AssertionError(UNREAD_RESULT_MESSAGE)


class RecordingSession(BaseSession):
    """Records the API methods a handler emits instead of calling Telegram."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []

    @override
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        """Record the outgoing method and answer with a result that refuses to be read."""
        self.requests.append(method)

        return cast("TelegramType", UnreadResult())

    @override
    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        """Refuse downloads: no covered flow reads files back from Telegram yet."""
        msg = "RecordingSession does not serve file downloads"
        raise NotImplementedError(msg)
        yield b""  # Never reached; keeps this an async generator, as the base class declares.

    @override
    async def close(self) -> None:
        """Nothing to release."""

    @property
    def answers(self) -> list[str]:
        """The text of every message the bot sent, in order."""
        return [request.text for request in self.requests if isinstance(request, SendMessage)]

    @property
    def last_answer(self) -> str:
        """The most recent reply; fails loudly when the handler stayed silent."""
        if not self.answers:
            msg = "Handler sent no reply"
            raise AssertionError(msg)
        return self.answers[-1]


def make_bot(session: RecordingSession) -> Bot:
    """Build a real ``Bot`` that talks to ``session`` instead of Telegram."""
    return Bot(token=TEST_BOT_TOKEN, session=session)


def make_message(bot: Bot, text: str = "") -> Message:
    """Build the incoming message a handler receives, bound to ``bot`` so replies reach its session."""
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=TEST_CHAT_ID, type="private"),
        from_user=User(id=TEST_USER_ID, is_bot=False, first_name="Test"),
        text=text,
    ).as_(bot)
