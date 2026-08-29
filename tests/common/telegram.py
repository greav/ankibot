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
from aiogram.methods import EditMessageText, SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Message, User

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
        self._queued_responses: dict[type[TelegramMethod[Any]], list[Any]] = {}

    def queue_response(self, method: type[TelegramMethod[TelegramType]], response: TelegramType) -> None:
        """Queue a real aiogram object to answer the next call to ``method`` this session receives.

        Keyed by method type rather than call order: an unrelated call (e.g. ``SendChatAction``, whose
        result no covered handler reads) never consumes a response queued for a different method.
        """
        self._queued_responses.setdefault(method, []).append(response)

    @override
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        """Record the outgoing method, answering with a queued response or one that refuses to be read."""
        self.requests.append(method)

        queue = self._queued_responses.get(type(method))
        if queue:
            return cast("TelegramType", queue.pop(0))
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
    def edits(self) -> list[str]:
        """The text of every message edit the bot sent, in order."""
        return [
            request.text
            for request in self.requests
            if isinstance(request, EditMessageText) and request.text is not None
        ]

    @property
    def last_edit(self) -> str:
        """The most recent edit; fails loudly when the handler edited nothing."""
        if not self.edits:
            msg = "Handler edited no message"
            raise AssertionError(msg)
        return self.edits[-1]

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


def make_message(
    bot: Bot, text: str = "", *, chat_id: int = TEST_CHAT_ID, user_id: int = TEST_USER_ID, message_id: int = 1
) -> Message:
    """Build a message bound to ``bot`` so replies reach its session.

    Doubles as the incoming update a handler receives, and as a queued response for a call a handler
    reads back (see ``RecordingSession.queue_response``) — ``message_id`` lets a test give the latter
    a distinctive id.
    """
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
    ).as_(bot)


def make_callback_query(
    bot: Bot,
    data: str,
    *,
    chat_id: int = TEST_CHAT_ID,
    user_id: int = TEST_USER_ID,
    message_text: str = "Choose a deck:",
) -> CallbackQuery:
    """Build the tap a handler receives, over the real picker message it was attached to.

    Fabricating input assumes nothing about how Telegram behaves; only reading a reply back would.
    """
    return CallbackQuery(
        id="1",
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        chat_instance="1",
        data=data,
        message=make_message(bot, text=message_text, chat_id=chat_id, user_id=user_id),
    ).as_(bot)
