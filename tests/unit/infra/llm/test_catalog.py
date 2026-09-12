"""The configured model catalog's own checks: what it refuses at start, and the order it keeps."""

import pytest

from ankibot.application.common.model_catalog import ModelOption
from ankibot.infra.llm.catalog import ConfigModelCatalog, ModelCatalogConfig, ModelEntryConfig


def entry(model_id: str) -> ModelEntryConfig:
    return ModelEntryConfig(id=model_id, provider="openai", label=model_id.upper())


async def test_user_can_get_the_reasoning_effort_the_operator_pinned() -> None:
    """A pinned effort travels with the option, and an entry without one carries none."""
    # Arrange
    pinned = ModelEntryConfig(id="a", provider="openai", label="A", reasoning_effort="none")
    catalog = ConfigModelCatalog(ModelCatalogConfig(default="a", models=(pinned, entry("b"))))

    # Act
    options = await catalog.options()

    # Assert
    assert [option.reasoning_effort for option in options] == ["none", None]


def test_bot_cannot_start_with_a_duplicate_model_id() -> None:
    """Two entries under one id would make a tap ambiguous, so the catalog refuses to build."""
    # Arrange
    config = ModelCatalogConfig(default="a", models=(entry("a"), entry("b"), entry("a")))

    # Act / Assert
    with pytest.raises(ValueError, match="more than once"):
        ConfigModelCatalog(config)


def test_bot_cannot_start_with_a_default_outside_the_list() -> None:
    """A default nobody could pick would serve every new user a model the keyboard never shows."""
    # Arrange
    config = ModelCatalogConfig(default="c", models=(entry("a"), entry("b")))

    # Act / Assert
    with pytest.raises(ValueError, match="'c'"):
        ConfigModelCatalog(config)


async def test_user_can_see_the_models_in_the_configured_order() -> None:
    """The keyboard lists models as the operator wrote them, with the default resolved by id."""
    # Arrange
    catalog = ConfigModelCatalog(ModelCatalogConfig(default="b", models=(entry("b"), entry("a"))))

    # Act
    options, default = await catalog.options(), await catalog.default()

    # Assert
    assert options == (ModelOption(id="b", label="B"), ModelOption(id="a", label="A"))
    assert default == ModelOption(id="b", label="B")
