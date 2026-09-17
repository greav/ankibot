"""The application half of the graph: every operation the presentation layer can invoke.

Interactors are REQUEST-scoped: they are stateless and cheap to build, and the scope is what will
hand them a per-update unit of work once one exists, without this file changing.
"""

from dishka import Provider, Scope, provide_all

from ankibot.application.add_snippet_cards import GenerateCards, SaveCards
from ankibot.application.add_vocabulary_word import GenerateCard, SaveCard, SuggestWords
from ankibot.application.anki_authentication import AuthenticateAnki
from ankibot.application.manage_cards import CreateCard
from ankibot.application.manage_decks import CreateDeck, ListDecks, RemoveDeck, SelectDeck
from ankibot.application.manage_models import ListModels, SelectModel


class InteractorProvider(Provider):
    """Registers every interactor; a new operation is one more name in the list below."""

    scope = Scope.REQUEST

    interactors = provide_all(
        AuthenticateAnki,
        CreateCard,
        ListDecks,
        SelectDeck,
        CreateDeck,
        RemoveDeck,
        ListModels,
        SelectModel,
        GenerateCard,
        SaveCard,
        SuggestWords,
        GenerateCards,
        SaveCards,
    )
