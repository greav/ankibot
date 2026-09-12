import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from ankibot.application.exceptions.base import ApplicationError
from ankibot.application.exceptions.models import ModelNotOfferedError
from ankibot.application.manage_models import ListModels, ListModelsRequest, SelectModel, SelectModelRequest
from ankibot.presentation.deck_picker import edit_into
from ankibot.presentation.identity import TelegramUserId
from ankibot.presentation.keyboards.models import ModelCallback, model_keyboard

logger = logging.getLogger(__name__)

router = Router()

CHOOSE_A_MODEL = "Choose a model:"
MODEL_GONE = "That model is no longer offered. Run /model again."
GENERIC_FAILURE = "Something went wrong. Please try again later."


@router.message(Command("model"))
async def model_cmd_handler(
    message: Message,
    list_models: FromDishka[ListModels],
    user_id: FromDishka[TelegramUserId],
) -> None:
    result = await list_models.execute(ListModelsRequest(user_id=user_id))
    await message.answer(CHOOSE_A_MODEL, reply_markup=model_keyboard(result.options, result.selected_id))


@router.callback_query(ModelCallback.filter())
async def model_selected_handler(
    callback: CallbackQuery,
    callback_data: ModelCallback,
    select_model: FromDishka[SelectModel],
    user_id: FromDishka[TelegramUserId],
) -> None:
    try:
        result = await select_model.execute(SelectModelRequest(user_id=user_id, model_id=callback_data.id))
    except ModelNotOfferedError:
        await edit_into(callback, MODEL_GONE)
    except ApplicationError as error:
        logger.warning("Failed to select a model: %s", error)
        await edit_into(callback, GENERIC_FAILURE)
    else:
        await edit_into(callback, f"Model set to {result.label}.")

    await callback.answer()
