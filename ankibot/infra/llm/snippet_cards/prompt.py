"""Prompts for distilling a reading passage into front/back cards.

The response's shape is not built here: ``chat.completions.parse`` derives the strict JSON schema
from the ``CardsAnswer`` model in ``parsing.py``.
"""

from collections.abc import Sequence

from openai.types.chat import ChatCompletionContentPartParam

from ankibot.application.add_snippet_cards import DraftCard, Snippet
from ankibot.infra.llm.images import image_data_url


def build_system_prompt(max_cards: int) -> str:
    """The system-turn prompt asking for at most ``max_cards`` cards grounded in the passage.

    The rules are the card-design canon of spaced repetition (Wozniak's twenty rules, Matuschak,
    Nielsen): a card is a retrieval task, so it must be atomic, have one stable answer, and be
    impossible to answer by recognition. The examples pin the rules down where a model tends to
    drift — enumerations, yes/no questions and whole-listing "explain this code" cards.
    """
    return (
        "You turn a passage a learner is reading into Anki flashcards for spaced repetition. "
        f"Create at most {max_cards} front/back cards. That limit is a ceiling, not a target: a "
        "typical passage yields two to four cards, and none when it holds nothing worth "
        "memorizing. Three strong cards beat eight weak ones; never pad to the limit. The passage "
        "is the source, not the script: it decides what the cards are about and what they claim, "
        "while the wording is yours — phrase each card as a standalone statement of knowledge, "
        "drawing on your own understanding of the subject to make it precise, but never make a "
        "card whose claim the passage does not support. Write the cards in the passage's own "
        "language. Reply with plain text only in every field — no HTML and no Markdown "
        "formatting, since the values are stored and shown verbatim.\n"
        "\n"
        "A card is a retrieval task, not a note. Every card must satisfy all of these:\n"
        "- Standalone: the card is reviewed months later, without the passage. Never refer to "
        'the passage, the chapter, the book, the author or "this text"; never say "here", '
        '"in this example" or "the second area". Someone who has never seen the passage must '
        "understand the question in full.\n"
        "- About the subject, not the text: never ask how the text is organized, why the author "
        "chose an example, what the chapter covers next, or what something is called in the "
        "passage. Ask about the subject matter itself.\n"
        "- Atomic: the front asks about exactly one thing; the back answers it in one short phrase "
        "or sentence.\n"
        "- One stable answer: the front has exactly one correct answer, so the learner can give the "
        "same answer every time. Never a front that several answers would satisfy.\n"
        "- Retrieval, not recognition: the answer must not be guessable from the front's wording, "
        "and the front must not contain or paraphrase the answer.\n"
        "- Earned by reading: someone who never saw the passage must not be able to answer from "
        "common sense or from the topic's name alone. If they could, the card tests nothing.\n"
        "- Not a flipped sentence: never make a card by asking for the second half of a sentence. "
        "Ask about what the passage claims, decides or explains, not about how it phrases it.\n"
        "- Never a yes/no or true/false question.\n"
        '- Never a list: no "list the", "name all", "what are the N". When the passage lists '
        "several items, a card goes only to an item carrying a non-obvious claim, and asks "
        "something specific about that item; or a fill-in-the-blank hides one item at a time.\n"
        "- No two cards with the same answer, and no two cards on the same point from angles that "
        "do not differ.\n"
        "\n"
        "What to pick. Prefer rules and decisions over isolated facts: what problem something "
        "solves, why it works, when to choose it, what it costs, how it differs from the "
        "similar thing next to it. When the passage contrasts two similar things, always make a "
        '"how does X differ from Y" card — that distinction is what the learner will confuse. '
        "When the passage illustrates a principle with an example, ask which principle the "
        "example shows or why the example works — that makes the learner apply the idea instead "
        "of repeating it. A central concept may earn several cards from different angles (its "
        "definition, its purpose, its trade-off). Skip trivia the learner would look up in "
        "seconds and not need again; a date, a number or a name earns a card only when the "
        "passage makes it matter.\n"
        "\n"
        "Fill-in-the-blank: a front may be a sentence from the passage with one key term replaced "
        "by ___, the back being that term alone. Use it for terminology, collocations, and code. "
        "Code is never memorized as a listing: a code card is a fragment of one to five lines with "
        "one blank or with a question about what it outputs, and the concept behind it is a "
        "separate card.\n"
        "\n"
        'Bad: "Describe the Observer pattern" (too broad, no stable answer). '
        'Bad: "What are the three parts of the pattern?" (a list). '
        'Bad: "Is Observer a behavioral pattern?" (yes/no). '
        'Bad: "What does the chapter mean by a subject?" (refers to the text). '
        'Bad: "Why does the author illustrate the pattern with a GUI example?" (about the text, '
        "not the subject). "
        'Good: "What problem does the Observer pattern solve?" — '
        '"Notifying subscribers not known in advance without coupling to them." '
        'Good: "Observer vs Pub/Sub: the key difference?" — '
        '"In Pub/Sub the publisher and subscriber never know each other; a broker sits between." '
        "Good: \"df.groupby('col').agg({'x': ___}) — the string that averages x\" — \"'mean'\""
    )


def kept_cards_note(kept: Sequence[DraftCard]) -> str:
    """The instruction listing the cards the learner already kept, so the model covers other facts."""
    listed = "\n".join(f"- {card.front} — {card.back}" for card in kept)
    return (
        "The learner already kept these cards from this passage. Do not repeat them; cover other "
        f"rules, decisions or distinctions the passage states:\n{listed}"
    )


def feedback_note(feedback: str) -> str:
    """The learner's note on what to change, framed as being about the cards being replaced."""
    return f"The learner asked to change this about the cards being replaced: {feedback}"


def build_user_content(
    snippet: Snippet, kept: Sequence[DraftCard] = (), feedback: str | None = None
) -> str | list[ChatCompletionContentPartParam]:
    """The user-turn content: the passage's text, or its screenshot as an image part.

    The hint, the kept cards and the feedback, whichever are present, follow the passage as
    further instructions in that order.
    """
    notes = []
    if snippet.hint is not None:
        notes.append(f"Focus on: {snippet.hint}")
    if kept:
        notes.append(kept_cards_note(kept))
    if feedback is not None:
        notes.append(feedback_note(feedback))

    if snippet.text is not None:
        return "\n\n".join([snippet.text, *notes])
    if snippet.image is not None:
        parts: list[ChatCompletionContentPartParam] = [{"type": "text", "text": note} for note in notes]
        parts.append({"type": "image_url", "image_url": {"url": image_data_url(snippet.image)}})
        return parts
    msg = "A snippet carries exactly one of text or image"  # Snippet.__post_init__ upholds this.
    raise ValueError(msg)
