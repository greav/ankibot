class ApplicationError(Exception):
    status_code = 500
    title = "Application error has occurred"
    detail = None
