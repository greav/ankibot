import pytest

from ankibot.infra.anki.authenticator import AnkiWebAuthenticatorConfig


@pytest.fixture(scope="session")
def anki_config() -> AnkiWebAuthenticatorConfig:
    """AnkiWeb adapter config. The password is distinctive so log assertions have something to bite on."""
    return AnkiWebAuthenticatorConfig(
        username="test-user@example.invalid",
        password="test-password-s3cr3t-not-real",
        ankiweb_base_url="https://ankiweb.net",
        ankiuser_base_url="https://ankiuser.net",
    )
