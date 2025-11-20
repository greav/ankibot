from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from ankibot.application.english_card_generation import (
    CardGenerationInputDTO,
    GenerateEnglishCardInteractor,
)
from ankibot.application.exceptions.card_generation import CardGenerationError


def build_router(interactor: GenerateEnglishCardInteractor) -> Router:
    router = Router(name="english_card_generation")

    @router.message(F.text)
    async def handle_word_message(message: Message) -> None:
        if not message.text:
            await message.answer("Please send a word to create a card.")
            return

        word = message.text.strip()
        if not word:
            await message.answer("Please send a non-empty word.")
            return

        dto = CardGenerationInputDTO(
            word=word,
            user_id=message.from_user.id if message.from_user else 0,
            chat_id=message.chat.id,
        )

        try:
            result = await interactor(dto)
        except CardGenerationError as exc:
            await message.answer(f"Unable to create card: {exc.title}")
            return

        if result.success:
            await message.answer(f"Card created successfully!\nWord: {word}\nAnki note id: {result.note_id}")
        else:
            await message.answer(result.error or "Failed to create card.")

    return router
