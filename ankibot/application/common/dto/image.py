from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Image:
    """An image the learner sent, as the bytes a generator will read."""

    data: bytes
    mime_type: str
