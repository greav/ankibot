______________________________________________________________________

## name: add-use-case description: >- Add business/application logic in the application layer following Clean Architecture: either a whole new use-case folder grouping the operations of one capability, or a single new operation (interactor) inside an existing capability — each operation an interactor (Command pattern), plus the ports (protocols) and DTOs it needs. Use this whenever the user wants a new capability OR a new operation on an existing one — e.g. "add card generation", "support user registration", "let admins delete a tag", "also let users rename a deck" — even if they don't use the words "use case", "operation", or "interactor".

# Add a new use case

Build the application-layer contracts first, before any implementation.
Naming, structure, and domain-model rules are in CLAUDE.md (Application layer /
Domain model / Naming) — follow them; this skill is only the procedure.

1. **Pick or create the use-case folder** `ankibot/application/<use_case_name>/`.
   One folder per capability, grouping several operations — not a single scenario.

1. **Domain model (only if needed):** add or update a plain anemic model under
   `application/` *only* if the use case must carry state; otherwise use DTOs.

1. **Define the ports** the operation needs (per the Ports / colocation rules in
   CLAUDE.md) as `Protocol`s named by role.

1. **Define the DTOs** (input and output), colocated with the interactor that uses
   them; lift shared ones to a use-case-level module or `application/common/`.

1. **Write one interactor per operation** (not per step), each in its own module,
   as a class with an `execute` method (see the Command-pattern rules in CLAUDE.md):

   ```python
   class CreateFlashcard:
       def __init__(self, generator: FlashcardGenerator) -> None:
           self._generator = generator

       async def execute(self, request: CreateFlashcardRequest) -> CreateFlashcardResult:
           ...
   ```

1. **Re-export each new interactor from the folder's `__init__.py`** and list it in
   `__all__`.

1. **Raise domain errors** from `ankibot/application/exceptions/`; model the
   alternative/error branches as explicit domain exceptions.

1. **Share, don't duplicate:** move a port/DTO used by another use case under
   `application/common/`.

1. **Wire it through the other layers so it can run:**

   - each new port needs an implementation — `/add-adapter`, wired in `bootstrap/`;
   - an operation becomes reachable once a handler calls it — `/add-handler`.

1. **Add tests** — interactors under `tests/unit/` through the `execute` boundary
   with fake ports, covering failure paths; handler/integration flows under
   `tests/integration/` where applicable.
