---
name: add-adapter
description: >-
  Add a new infrastructure adapter that implements an existing application port, together with its per-class configuration contract and bootstrap wiring. Use this whenever the user wants to connect the bot to a concrete external service, technology, or provider — e.g. "add an OpenAI implementation", "store cards in Postgres", "add an AnkiConnect client", or "add an in-memory/fake version for tests" — even if they don't say "adapter".
---

# Add a new adapter (port implementation)

Infrastructure, Naming, and Configuration rules are in CLAUDE.md — follow them;
this skill is only the procedure.

1. **Identify the port** in `ankibot/application/` that this adapter implements.
   If it does not exist yet, define it first via `/add-use-case`.

2. **Create the adapter** in `ankibot/infra/`, named `<ProviderOrTechnology><InterfaceName>`.

3. **Define the config contract** as a dataclass in the same module; the constructor
   takes a single `config` argument:

   ```python
   @dataclass
   class OpenAIFlashcardGeneratorConfig:
       api_key: str
       model: str

   class OpenAIFlashcardGenerator:
       def __init__(self, config: OpenAIFlashcardGeneratorConfig) -> None:
           self._config = config
   ```

4. **Add config values** to `configs/config.yaml` (`${oc.env:VAR,default}` for secrets),
   and add the config dataclass as a field on the root `Config` in `bootstrap/config.py`.

5. **Wire it in `bootstrap/`:** construct the adapter from its config and inject it
   where the port is required.

6. **Add tests**; provide a fake/in-memory adapter if it helps test the use case
   in isolation.
