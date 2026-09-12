from ankibot.application.exceptions.base import ApplicationError


class ModelNotOfferedError(ApplicationError):
    """The picked model id is not in the catalog: the keyboard predates a config change, or the id was forged."""

    message = "That model is not offered"
