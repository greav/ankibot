from httpx import Cookies

from ankibot.application.protocols import CookieStorage


class InMemoryCookieStorage(CookieStorage):
    """In-memory implementation of cookie storage."""

    def __init__(self) -> None:
        self._cookies: dict[str, Cookies] = {}

    async def store_cookies(self, key: str, cookies: Cookies) -> None:
        """Store cookies for a given key."""
        self._cookies[key] = cookies

    async def get_cookies(self, key: str) -> Cookies | None:
        """Retrieve cookies for a given key. Returns None if not found."""
        return self._cookies.get(key)

    async def clear_cookies(self, key: str) -> None:
        """Clear cookies for a given key."""
        self._cookies.pop(key, None)
