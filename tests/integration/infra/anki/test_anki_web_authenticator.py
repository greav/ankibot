import asyncio
import logging

import httpx
import pytest

from ankibot.application.exceptions.anki import (
    AnkiAuthenticationError,
    AnkiInvalidPasswordError,
    AnkiInvalidUsernameError,
)
from ankibot.infra.anki.authenticator import AnkiWebAuthenticator, AnkiWebAuthenticatorConfig
from ankibot.infra.logger import LoggerConfig, configure_root_logger
from ankiweb.account.login_pb2 import (
    LOGIN_RESPONSE_STATUS_AUTHENTICATED,
    LOGIN_RESPONSE_STATUS_INVALID_PASS,
    LOGIN_RESPONSE_STATUS_INVALID_USER,
    LOGIN_RESPONSE_STATUS_UNKNOWN,
    LoginResponse,
    LoginResponseStatus,
)
from tests.common.transport import Handler, client_for

TOKEN = "test-exchange-token"


def build_handler(
    login_status: LoginResponseStatus,
    *,
    exchange_sets_cookie: bool = True,
    exchange_status_code: int = 303,
) -> Handler:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "ankiweb.net" and request.url.path == "/svc/account/login":
            response = LoginResponse(status=login_status)
            if login_status == LOGIN_RESPONSE_STATUS_AUTHENTICATED:
                response.token = TOKEN
            headers = (
                {"Set-Cookie": "ankiweb_session=abc; Domain=ankiweb.net; Path=/"}
                if login_status == LOGIN_RESPONSE_STATUS_AUTHENTICATED
                else {}
            )
            return httpx.Response(200, content=response.SerializeToString(), headers=headers)

        if request.url.host == "ankiuser.net" and request.url.path == "/account/ankiuser-login":
            assert request.url.params["t"] == TOKEN
            # The real endpoint answers with a 303 that carries the session cookie; following it
            # would land on a path this handler rejects, guarding the "do not follow" contract.
            headers = {"Location": "https://ankiuser.net/decks"}
            if exchange_sets_cookie:
                headers["Set-Cookie"] = "ankiuser_session=xyz; Domain=ankiuser.net; Path=/"
            return httpx.Response(exchange_status_code, headers=headers)

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


def client_cookie_domains(client: httpx.AsyncClient) -> set[str]:
    return {cookie.domain for cookie in client.cookies.jar}


async def test_user_can_authenticate_with_valid_credentials(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A successful login leaves the client holding a session for both AnkiWeb domains."""
    # Arrange
    async with client_for(build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED)) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)

        # Act
        await authenticator.authenticate()

        # Assert
        domains = client_cookie_domains(client)
        assert any(domain.endswith("ankiweb.net") for domain in domains)
        assert any(domain.endswith("ankiuser.net") for domain in domains)


async def test_user_cannot_authenticate_with_an_unknown_username(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A rejected username surfaces as its own error, so the bot can name the field at fault."""
    # Arrange
    async with client_for(build_handler(LOGIN_RESPONSE_STATUS_INVALID_USER)) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)

        # Act / Assert
        with pytest.raises(AnkiInvalidUsernameError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_with_a_wrong_password(anki_config: AnkiWebAuthenticatorConfig) -> None:
    """A rejected password surfaces as its own error, so the bot can name the field at fault."""
    # Arrange
    async with client_for(build_handler(LOGIN_RESPONSE_STATUS_INVALID_PASS)) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)

        # Act / Assert
        with pytest.raises(AnkiInvalidPasswordError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_on_an_unrecognized_login_status(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A login status we do not recognize fails rather than being read as success."""
    # Arrange
    async with client_for(build_handler(LOGIN_RESPONSE_STATUS_UNKNOWN)) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)

        # Act / Assert
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_when_login_returns_an_http_error(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A non-200 from the login endpoint fails instead of being parsed as a login response."""

    # Arrange — AnkiWeb answers the login endpoint with a server error
    async def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(500)

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_when_ankiweb_is_unreachable(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A transport failure on login becomes an application error, so /auth still answers the user."""

    # Arrange — the login request never reaches AnkiWeb
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_when_the_token_exchange_is_unreachable(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A transport failure after a successful login also becomes an application error."""
    # Arrange — login succeeds, the ankiuser.net exchange never connects
    login = build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "ankiuser.net":
            raise httpx.ConnectError("connection refused", request=request)
        return await login(request)

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_when_the_token_exchange_sets_no_cookie(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """A token exchange that returns no ankiuser.net cookie is a failure, not a silent success."""
    # Arrange
    handler = build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED, exchange_sets_cookie=False)

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_when_the_token_exchange_is_refused(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """An error status from the token exchange fails the whole authentication."""
    # Arrange
    handler = build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED, exchange_status_code=403)

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_find_their_password_in_the_logs(
    anki_config: AnkiWebAuthenticatorConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The configured password never reaches the log stream, even at DEBUG level."""
    # Arrange
    async with client_for(build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED)) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)

        # Act
        with caplog.at_level(logging.DEBUG):
            await authenticator.authenticate()

    # Assert
    assert anki_config.password not in caplog.text


async def test_user_cannot_find_the_login_token_in_the_logs(
    anki_config: AnkiWebAuthenticatorConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Under the bot's logging setup the token exchange URL, ticket included, stays out of the log.

    httpx reports every request's full URL at INFO; the bot's root logger configuration is what
    keeps that line out, so the test runs under it rather than under pytest's bare capture.
    """
    # Arrange
    root_logger = configure_root_logger(LoggerConfig(level="DEBUG", fmt="%(message)s"))
    stream_handler = root_logger.handlers[-1]
    try:
        async with client_for(build_handler(LOGIN_RESPONSE_STATUS_AUTHENTICATED)) as client:
            authenticator = AnkiWebAuthenticator(anki_config, client)

            # Act
            with caplog.at_level(logging.DEBUG):
                await authenticator.authenticate()
    finally:
        root_logger.removeHandler(stream_handler)

    # Assert
    assert TOKEN not in caplog.text


async def test_user_cannot_authenticate_when_ankiweb_serves_html(anki_config: AnkiWebAuthenticatorConfig) -> None:
    """An HTML page served with 200 surfaces as AnkiAuthenticationError, not a raw protobuf DecodeError.

    Without this, the decode failure escapes the ApplicationError hierarchy, the /auth handler's
    except-chain misses it, and the user gets no reply at all.
    """

    # Arrange — AnkiWeb answers the login endpoint with a maintenance page instead of protobuf
    async def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(200, content=b"<html><body>maintenance</body></html>")

    # Act / Assert
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        with pytest.raises(AnkiAuthenticationError):
            await authenticator.authenticate()


async def test_user_cannot_authenticate_twice_on_one_exchange_cookie(
    anki_config: AnkiWebAuthenticatorConfig,
) -> None:
    """Two parallel authentications each judge success on their own exchange response, not the shared jar.

    The client's cookie jar is process-wide, so a naive check against it would let a second
    authentication pass on the cookie the first one deposited. Here only the first exchange sets
    the cookie, so exactly one attempt must succeed.
    """
    # Arrange — only the first token exchange returns a session cookie
    exchange_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal exchange_calls

        if request.url.host == "ankiweb.net":
            response = LoginResponse(status=LOGIN_RESPONSE_STATUS_AUTHENTICATED)
            response.token = TOKEN
            return httpx.Response(
                200,
                content=response.SerializeToString(),
                headers={"Set-Cookie": "ankiweb_session=abc; Domain=ankiweb.net; Path=/"},
            )

        exchange_calls += 1
        headers = {"Location": "https://ankiuser.net/decks"}
        if exchange_calls == 1:
            headers["Set-Cookie"] = "ankiuser_session=xyz; Domain=ankiuser.net; Path=/"
        return httpx.Response(303, headers=headers)

    # Act
    async with client_for(handler) as client:
        authenticator = AnkiWebAuthenticator(anki_config, client)
        results = await asyncio.gather(
            authenticator.authenticate(),
            authenticator.authenticate(),
            return_exceptions=True,
        )

    # Assert
    failures = [result for result in results if isinstance(result, BaseException)]
    assert len(failures) == 1, f"expected exactly one failure, got {results}"
    assert isinstance(failures[0], AnkiAuthenticationError)
