from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CardTemplate:
    """The named, ordered set of fields one kind of card carries."""

    name: str
    fields: tuple[str, ...]


def missing_fields(template: CardTemplate, values: Mapping[str, str]) -> tuple[str, ...]:
    """Template fields ``values`` leaves unfilled — absent, or blank after stripping."""
    return tuple(field for field in template.fields if not values.get(field, "").strip())


def in_template_order(template: CardTemplate, values: Mapping[str, str]) -> tuple[str, ...]:
    """``values`` ordered as the template lists its fields; keys outside the template are dropped."""
    return tuple(values[field] for field in template.fields if field in values)
