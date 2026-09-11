"""How a generation failure reads in the log: the error, and the SDK error class behind it."""


def failure_reason(error: BaseException) -> str:
    """``error``'s message, with the class of what caused it when there is one — never a payload."""
    cause = error.__cause__
    return f"{error} ({type(cause).__name__})" if cause is not None else str(error)
