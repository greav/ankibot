import pytest

from ankibot.infra.anki.authenticator import AnkiWebAuthenticatorConfig
from ankibot.infra.anki.card_gateway import AnkiWebCardGatewayConfig


@pytest.fixture(scope="session")
def anki_config() -> AnkiWebAuthenticatorConfig:
    """AnkiWeb adapter config. The password is distinctive so log assertions have something to bite on."""
    return AnkiWebAuthenticatorConfig(
        username="test-user@example.invalid",
        password="test-password-s3cr3t-not-real",
        ankiweb_base_url="https://ankiweb.net",
        ankiuser_base_url="https://ankiuser.net",
    )


@pytest.fixture(scope="session")
def card_gateway_config() -> AnkiWebCardGatewayConfig:
    """AnkiWebCardGateway adapter config, pointed at the same obviously-fake host as ``anki_config``."""
    return AnkiWebCardGatewayConfig(ankiuser_base_url="https://ankiuser.net")
