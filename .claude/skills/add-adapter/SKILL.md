---
name: add-adapter
description: >-
  Add a new infrastructure adapter that implements an existing application port, together with its per-class configuration contract and bootstrap wiring. Use this whenever the user wants to connect the bot to a concrete external service, technology, or provider — e.g. "add an OpenAI implementation", "store cards in Postgres", "add an AnkiConnect client", or "add an in-memory/fake version for tests" — even if they don't say "adapter".
---

# Add a new adapter (port implementation)

Infrastructure, Naming, and Configuration rules are in AGENTS.md — follow them;
this skill is only the procedure.

1. **Identify the port** in `ankibot/application/` that this adapter implements.
   If it does not exist yet, define it first via `/add-use-case`.

2. **Create the adapter** in `ankibot/infra/`, named `<ProviderOrTechnology><InterfaceName>`.

3. **Define the config contract** as a dataclass in the same module; the constructor
   takes a single `config` argument:

   ```python
   @dataclass(frozen=True, kw_only=True)
   class OpenAIFlashcardGeneratorConfig:
       api_key: str
       model: str

   class OpenAIFlashcardGenerator:
       def __init__(self, config: OpenAIFlashcardGeneratorConfig) -> None:
           self._config = config
   ```

4. **Add config values** to `configs/config.yaml` (`${oc.env:VAR,default}` for secrets),
   and add the config dataclass as a field on the root `Config` in `bootstrap/config.py`.
   Add the matching key to `.env.example` when the reference has no default.

5. **Expose the config to the graph** — one method on `ConfigProvider`
   (`bootstrap/di/providers/config.py`), returning the field and annotated with its type:

   ```python
   @provide
   def openai_flashcard_generator(self) -> OpenAIFlashcardGeneratorConfig:
       return self._config.openai_flashcard_generator
   ```

   `bootstrap/di/container.py` does not change.

6. **Register the adapter** in `AdapterProvider` (`bootstrap/di/providers/adapter.py`).
   Because the adapter subclasses its port, that is one line:

   ```python
   flashcard_generator = provide(WithParents[OpenAIFlashcardGenerator])
   ```

   Write a `@provide` method instead only when the factory has to choose between
   implementations, or holds a client that must be closed:

   ```python
   @provide
   async def flashcard_generator(self, config: OpenAIFlashcardGeneratorConfig) -> AsyncIterator[FlashcardGenerator]:
       client = build_openai_client(config)
       yield OpenAIFlashcardGenerator(config, client)
       await client.close()
   ```

7. **Add the port to `warm_up`** (`bootstrap/di/warm_up.py`) if it is a new one.

8. **Add tests**; provide a fake/in-memory adapter so the operations depending on
   this port can be covered without real infrastructure. A new port also needs a
   constructor argument and a matching `@provide` method on `FakePortProvider`
   (`tests/common/fakes/ports.py`), plus a fixture and an autouse reset in
   `tests/integration/bot/conftest.py`.
