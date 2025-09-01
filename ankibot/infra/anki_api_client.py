import logging
from typing import Any

import httpx

from ankibot.application.protocols import AnkiApiClient, CookieStorage
from ankibot.proto_gen import auth_pb2, decks_pb2, notes_pb2

logger = logging.getLogger(__name__)


class AnkiApiClientImpl(AnkiApiClient):
    """Implementation of Anki API client using httpx for async operations."""

    def __init__(self, cookie_storage: CookieStorage) -> None:
        self._cookie_storage = cookie_storage
        self._ankiweb_base_url = "https://ankiweb.net"
        self._ankiuser_base_url = "https://ankiuser.net"
        self._timeout = 30.0

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with Anki web service. Returns True if successful."""
        try:
            # Step 1: Authenticate with ankiweb.net
            auth_payload = auth_pb2.Auth(username=username, password=password).SerializeToString()

            async with httpx.AsyncClient() as client:
                auth_response = await client.post(
                    f"{self._ankiweb_base_url}/svc/account/login",
                    content=auth_payload,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self._timeout,
                )
                auth_response.raise_for_status()

                auth_message = auth_pb2.AuthResponse.FromString(auth_response.content)
                if auth_message.status != auth_pb2.AuthResponse.Status.AUTHENTICATED:
                    logger.warning(f"Authentication failed with status: {auth_message.status}")
                    return False

                # Store ankiweb cookies
                await self._cookie_storage.store_cookies("ankiweb", auth_response.cookies)

                # Step 2: Authenticate with ankiuser.net using the token
                ankiuser_auth_response = await client.get(
                    f"{self._ankiuser_base_url}/account/ankiuser-login",
                    params={"t": auth_message.token},
                    follow_redirects=True,
                    timeout=self._timeout,
                )
                ankiuser_auth_response.raise_for_status()

                # Store ankiuser cookies from the client's cookie jar (filter for ankiuser domain)
                ankiuser_cookies = httpx.Cookies()
                for cookie in client.cookies.jar:
                    if cookie.domain and "ankiuser.net" in cookie.domain:
                        ankiuser_cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
                await self._cookie_storage.store_cookies("ankiuser", ankiuser_cookies)

                logger.info("Successfully authenticated with Anki services")
                return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def get_decks_info(self) -> list[dict[str, Any]]:
        """Get information about available decks."""
        try:
            ankiweb_cookies = await self._cookie_storage.get_cookies("ankiweb")
            if not ankiweb_cookies:
                raise ValueError("Not authenticated with ankiweb")

            decks_payload = decks_pb2.DecksInfo().SerializeToString()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._ankiweb_base_url}/svc/decks/deck-list-info",
                    content=decks_payload,
                    cookies=ankiweb_cookies,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self._timeout,
                )
                response.raise_for_status()

                decks_info_msg = decks_pb2.DecksInfoResponse.FromString(response.content)
                return self._parse_decks_info(decks_info_msg)

        except Exception as e:
            logger.error(f"Failed to get decks info: {e}")
            return []

    async def get_info_for_adding(self) -> dict[str, Any]:
        """Get information needed for adding cards (note types, fields, etc.)."""
        try:
            ankiuser_cookies = await self._cookie_storage.get_cookies("ankiuser")
            if not ankiuser_cookies:
                raise ValueError("Not authenticated with ankiuser")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._ankiuser_base_url}/svc/editor/get-info-for-adding",
                    cookies=ankiuser_cookies,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self._timeout,
                )
                response.raise_for_status()

                info_message = notes_pb2.GetInfoResponse.FromString(response.content)
                return self._parse_info_for_adding(info_message)

        except Exception as e:
            logger.error(f"Failed to get info for adding: {e}")
            return {}

    async def add_card(self, front: str, back: str, deck_id: int, notetype_id: int, tags: str = "") -> bool:
        """Add a new card to the specified deck. Returns True if successful."""
        try:
            ankiuser_cookies = await self._cookie_storage.get_cookies("ankiuser")
            if not ankiuser_cookies:
                raise ValueError("Not authenticated with ankiuser")

            add_payload = notes_pb2.AddOrUpdateRequest(
                fields=[front, back],
                tags=tags,
                add=notes_pb2.AddOrUpdateRequest.AddMode(notetype_id=notetype_id, deck_id=deck_id),
            ).SerializeToString()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._ankiuser_base_url}/svc/editor/add-or-update",
                    content=add_payload,
                    cookies=ankiuser_cookies,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self._timeout,
                )
                response.raise_for_status()

                logger.info(f"Successfully added card to deck {deck_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to add card: {e}")
            return False

    def _parse_decks_info(self, decks_info: decks_pb2.DecksInfoResponse) -> list[dict[str, Any]]:
        """Parse DecksInfoResponse into a list of deck dictionaries."""
        decks = []

        def parse_deck(deck: decks_pb2.Deck) -> dict[str, Any]:
            return {
                "id": deck.deck_id,
                "name": deck.name,
                "level": deck.level,
                "collapsed": deck.collapsed,
                "review_count": deck.review_count,
                "learn_count": deck.learn_count,
                "new_count": deck.new_count,
                "total_in_deck": deck.total_in_deck,
                "children": [parse_deck(child) for child in deck.children],
            }

        if decks_info.top_node:
            decks.append(parse_deck(decks_info.top_node))

        return decks

    def _parse_info_for_adding(self, info: notes_pb2.GetInfoResponse) -> dict[str, Any]:
        """Parse GetInfoResponse into a dictionary with note types, decks, and fields."""
        return {
            "notetypes": [{"id": nt.id, "name": nt.name} for nt in info.notetypes],
            "decks": [{"id": deck.id, "name": deck.name} for deck in info.decks],
            "current_deck_id": info.current_deck_id,
            "current_notetype_id": info.current_notetype_id,
            "fields": [
                {
                    "ord": field.ord.val,
                    "name": field.name,
                    "config": {
                        "sticky": field.config.sticky,
                        "rtl": field.config.rtl,
                        "font_name": field.config.font_name,
                        "font_size": field.config.font_size,
                        "description": field.config.description,
                        "plain_text": field.config.plain_text,
                    },
                }
                for field in info.fields
            ],
        }
