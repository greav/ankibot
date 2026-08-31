"""
Use case: Anki Authentication.

Actor: Operator
Operator establishes the AnkiWeb session every other use case reads and writes through.
"""

from ankibot.application.anki_authentication.authenticate_anki import AuthenticateAnki

__all__ = ["AuthenticateAnki"]
