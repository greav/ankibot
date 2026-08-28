import logging
from dataclasses import dataclass
from typing import override

import httpx
from google.protobuf.message import DecodeError

from ankibot.application.anki_authentication.authenticate_anki import AnkiAuthenticator
from ankibot.application.exceptions.anki import (
    AnkiAuthenticationError,
    AnkiInvalidPasswordError,
    AnkiInvalidUsernameError,
)
from ankibot.infra.anki.protobuf import PROTOBUF_CONTENT_TYPE
from ankiweb.account.login_pb2 import (
    LOGIN_RESPONSE_STATUS_AUTHENTICATED,
    LOGIN_RESPONSE_STATUS_INVALID_PASS,
    LOGIN_RESPONSE_STATUS_INVALID_USER,
    LoginRequest,
    LoginResponse,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnkiWebAuthenticatorConfig:
    username: str
    password: str
    ankiweb_base_url: str
    ankiuser_base_url: str


class AnkiWebAuthenticator(AnkiAuthenticator):
    """Authenticates against AnkiWeb's two-domain cookie session model.

    See docs/ankiweb-auth.md for the flow this implements.
    """

    def __init__(self, config: AnkiWebAuthenticatorConfig, client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = client

    @override
    async def authenticate(self) -> None:
        # Authentication is currently a side effect: the session cookies end up in the shared
        # httpx client's jar and authorize subsequent in-process requests. Once we support
        # cross-restart persistence or multi-user, we must capture the session cookies and
        # store them per user (see docs/multi-user-auth.md) instead of relying on this jar.
        login_response = await self._login()

        if login_response.status == LOGIN_RESPONSE_STATUS_INVALID_USER:
            raise AnkiInvalidUsernameError
        if login_response.status == LOGIN_RESPONSE_STATUS_INVALID_PASS:
            raise AnkiInvalidPasswordError
        if login_response.status != LOGIN_RESPONSE_STATUS_AUTHENTICATED:
            raise AnkiAuthenticationError

        exchange_response = await self._exchange_token(login_response.token)

        # Confirm on the exchange response itself (scoped to this attempt), not on the shared
        # jar. This relies on not following the redirect — see _exchange_token.
        has_ankiuser_cookie = any(cookie.domain.endswith("ankiuser.net") for cookie in exchange_response.cookies.jar)
        if not has_ankiuser_cookie:
            raise AnkiAuthenticationError("AnkiWeb did not set an ankiuser.net session cookie")

        logger.info("Authenticated with AnkiWeb")

    async def _login(self) -> LoginResponse:
        request = LoginRequest(username=self._config.username, password=self._config.password)
        try:
            response = await self._client.post(
                f"{self._config.ankiweb_base_url}/svc/account/login",
                content=request.SerializeToString(),
                headers={"Content-Type": PROTOBUF_CONTENT_TYPE},
            )
        except httpx.HTTPError as error:
            raise AnkiAuthenticationError("Failed to reach AnkiWeb login endpoint") from error

        if response.status_code != httpx.codes.OK:
            raise AnkiAuthenticationError(f"AnkiWeb login returned HTTP {response.status_code}")

        login_response = LoginResponse()
        try:
            login_response.ParseFromString(response.content)
        except DecodeError as error:
            # A 200 carrying HTML (error page, captcha, login form) decodes as garbage protobuf.
            # Without this, DecodeError escapes ApplicationError handling and the user gets silence.
            raise AnkiAuthenticationError("AnkiWeb login returned a non-protobuf response") from error
        return login_response

    async def _exchange_token(self, token: str) -> httpx.Response:
        try:
            # Do not follow the redirect: the ankiuser.net session cookie is set via Set-Cookie
            # on this response (a 303), so the caller must read it from this response directly.
            response = await self._client.get(
                f"{self._config.ankiuser_base_url}/account/ankiuser-login",
                params={"t": token},
                follow_redirects=False,
            )
        except httpx.HTTPError as error:
            raise AnkiAuthenticationError("Failed to reach AnkiWeb token-exchange endpoint") from error

        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise AnkiAuthenticationError(f"AnkiWeb token exchange returned HTTP {response.status_code}")

        return response
