---
name: add-use-case
description: >-
  Add business/application logic in the application layer following Clean Architecture: either a whole new use-case folder grouping the operations of one capability, or a single new operation (interactor) inside an existing capability — each operation an interactor (Command pattern), plus the ports (protocols) and DTOs it needs. Use this whenever the user wants a new capability OR a new operation on an existing one — e.g. "add card generation", "support user registration", "let admins delete a tag", "also let users rename a deck" — even if they don't use the words "use case", "operation", or "interactor".
---

# Add a new use case

Build the application-layer contracts first, before any implementation.
Naming, structure, and domain-model rules are in AGENTS.md (Application layer /
Domain model / Naming) — follow them; this skill is only the procedure.

1. **Pick or create the use-case folder** `ankibot/application/<use_case_name>/`.
   One folder per capability, grouping several operations — not a single scenario.

2. **Domain (only if needed):** a rule goes to `ankibot/domain/` only if it would
   survive replacing AnkiWeb — see the placement test in AGENTS.md. State the use
   case merely carries between steps is a plain dataclass under `application/`;
   pure input/output shapes are DTOs. Do not add a value object by default.

3. **Define the ports** the operation needs (per the Ports / colocation rules in
   AGENTS.md) as `Protocol`s named by role.

4. **Define the DTOs** (input and output), colocated with the interactor that uses
   them; lift shared ones to a use-case-level module or `application/common/`.

5. **Write one interactor per operation** (not per step), each in its own module,
   as a class with an `execute` method (see the Command-pattern rules in AGENTS.md):

   ```python
   class CreateFlashcard:
       def __init__(self, generator: FlashcardGenerator) -> None:
           self._generator = generator

       async def execute(self, request: CreateFlashcardRequest) -> CreateFlashcardResult:
           ...
   ```

6. **Re-export each new interactor from the folder's `__init__.py`** and list it in
   `__all__`.

7. **Raise custom errors** from `ankibot/application/exceptions/` — or
   `domain/errors.py` when a domain object itself raises. Model every alternative
   branch as an explicit exception, raised from the interactor rather than from a
   rule function.

8. **Share, don't duplicate:** move a port/DTO used by another use case under
   `application/common/`.

9. **Wire it through the other layers so it can run:**

   - **register the interactor** in `InteractorProvider`
     (`bootstrap/di/providers/interactor.py`) — one more name in its `provide_all(...)`
     list, and every handler asking for `FromDishka[TheInteractor]` gets one;
   - each new port needs an implementation — `/add-adapter`, which also registers it in
     `AdapterProvider`;
   - an operation becomes reachable once a handler calls it — `/add-handler`.

10. **Add tests** — cover the operation through the handler that calls it, under
   `tests/integration/`, with a fake for each port and one test per failure path.
   Do **not** add a unit test isolating the interactor with fake ports: a delegating
   interactor has nothing to assert but the delegation. If the operation carries a
   rule worth many cases, extract that rule into a plain function and unit-test the
   function under `tests/unit/`. See AGENTS.md (Domain model, Testing).
