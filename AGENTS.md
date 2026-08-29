# ankibot

Telegram bot that turns Telegram messages into Anki flashcards for spaced-repetition learning. Target users: language learners, students, and anyone using spaced repetition for knowledge retention.

## Architecture principles

- **Clean Architecture** — separate concerns across `application`, `infra`, `presentation`.
- **Dependency Inversion** — the application layer defines interfaces (protocols); the infrastructure layer provides implementations. Implementations adapt to the interface, never the other way around.
- **Single Responsibility** — each module has one well-defined purpose.
- **Business-first interfaces** — interfaces are shaped by use-case needs, not by any concrete provider or transport. Never leak HTTP/SQL/API-client specifics into a contract.

## Layer map

- `ankibot/domain/` — the rules of the subject matter itself: domain functions, records, value objects, entities, and the errors they raise. It imports from no other layer. Ports and DTOs belong to `application/` — see Domain model for the line between a DTO and a domain record.
- `ankibot/application/` — application logic: use cases, interactors, DTOs, and interface definitions (protocols). It may import `domain`; it must not import from `infra` or `presentation` — dependencies point inward.
  - `application/exceptions/` holds errors raised by use cases; errors raised by domain objects live in `domain/errors.py`, under a shared root so one `except` still catches both;
  - `application/common/` holds interfaces and DTOs shared across use cases.
- `ankibot/infra/` — infrastructure and external-service adapters (API clients, DB adapters, logging). Adapters implement the protocols defined in `application/`.
- `ankibot/presentation/` — user-facing layer (Telegram commands and handlers).
  - `presentation/handlers/` holds message handlers; each handler module owns a `Router`.
  - `presentation/keyboards/` holds router-free keyboard builders and callback-data factories shared by handler modules — a module owning a `Router` cannot be imported by another handler module without attaching it twice.
- `ankibot/bootstrap/` — initialization and dependency injection. Dependencies are composed here and injected into handlers/services.
  - `bot.py` wires routers and startup;
  - `config.py` loads configuration via OmegaConf into the root `Config`.

## Application layer conventions

- **Structure by capability, not by type.** Each **use case is a folder** grouping the related **operations** of one capability; each operation is its own module. Never create cross-cutting `interactors/`, `dtos/`, or `ports/` folders that slice the layer by type. (Folder/module/interactor naming: see Naming.)
- **Expose interactors through the folder's `__init__.py`:** re-export every interactor (`from .create_card import CreateCard`) and list it in `__all__`, so callers import from the use-case package (`from ankibot.application.manage_cards import CreateCard`), not from operation modules.
- **Interactors (Command pattern):** one class per operation with an `execute` method (input DTO → output DTO / domain object), invoked from presentation, never the reverse. `execute` orchestrates that operation's own steps — port calls and business-logic calls (a domain function, a domain object's method, a local helper, an inline rule) — and returns a DTO. An interactor **never calls another interactor** and **never touches `infra`** (no HTTP/SQL/SDK clients); factor a shared step into a plain helper or a port/DTO under `application/common/`.
- **Ports:** when an operation needs infra (persistence, cache, storage, auth, HTTP, external API), depend on a **port** — a `Protocol` named by role, free of transport/library specifics, defined here before any implementation; the adapter lives in `infra/`.
- **Colocate ports and DTOs with the interactor that uses them** — by default in the operation's own module. Exceptions: shared by several interactors **within one use case** → a use-case-level module (`ports.py`, `dto.py`); shared **across use cases** → `application/common/` (DTOs under `application/common/dto/`). Never duplicate a shared port or DTO across use-case folders.
- **Errors:** raise custom exceptions — from `application/exceptions/` for use-case failures, from `domain/errors.py` for rule violations — never transport- or library-specific ones.
- To add a use case, prefer the `/add-use-case` skill.

## Domain model

- **Placement test.** `ankibot/domain/` holds the rules that would survive replacing AnkiWeb with another flashcard backend. A rule shaped by one request, or by AnkiWeb's format, stays in `application/` or `infra/`.
- **Ports stay out.** A port is written from a use case's need, not from the subject matter, so it lives in `application/` — even when it returns domain types.
- **DTOs are shaped by a boundary; domain records are shaped by the subject.** A request body, a response, a read model assembled for one screen is a DTO and lives in `application/`. A structure that means something in the subject matter is a domain record and lives here — with or without methods. A record is not an entity.
- **A domain rule never takes an application DTO.** The import direction settles it: give the rule plain values, or have the reader port return a domain type. Reach for the domain type only when a cluster of fields must travel together.
- **Group by subject, not by type.** `domain/session.py`, `domain/scheduling.py` — never `value_objects/` or `entities/` folders.
- **The domain stays small.** This bot mostly relays state it does not own: a card's life continues in AnkiWeb, not here. State we do not own never becomes an entity.
- **Orchestration stays in `execute`.** Decisions taken on what a port returned cannot be extracted without dragging the ports along; they are covered through the handler.
- **Rules get extracted.** Anything computable from data already in hand — parsing, validation, formatting, scheduling arithmetic — leaves `execute` and is unit-tested directly: into `domain/` when it passes the placement test, otherwise into a helper in the operation's own module.
- **Raise from the interactor, not from the rule.** The rule answers a question; the interactor decides what to do with the answer.

### Which shape to reach for

These are independent options, not a sequence to climb: an entity with no value objects is normal, and a domain of plain functions is a legitimate end state.

| Reach for                                        | When                                                                                                           |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| a plain function                                 | the rule is computable from data in hand                                                                       |
| a frozen dataclass with no validation (a record) | several fields travel together                                                                                 |
| a value object validating in `__post_init__`     | **several correlated fields** carry an invariant that would otherwise be re-checked at every construction site |
| an entity with behavior                          | **we own the state**: it has identity, a lifecycle, and transitions that can be violated                       |

Default to the first two. A value object wrapping a single primitive is almost never worth its cost: a type alias (`type CardId = UUID`) names the concept, and a plain function validates at the one entry point where it matters. Do not populate the domain ahead of a rule that needs it.

## Presentation layer conventions

Each handler module creates its own `Router()` and registers handlers with decorators (e.g. `@router.message(CommandStart())`); routers are included in `bootstrap/bot.py` via `dp.include_router(<module>.router)`.

A handler is a thin controller with no business logic. For each request it should:

1. build the input DTO from the incoming Telegram message,
1. call the interactor for that operation (`interactor.execute(dto)`),
1. map the returned DTO / domain object to a Telegram response.

To add a handler, prefer the `/add-handler` skill so wiring into `bootstrap/bot.py` is not forgotten.

## Infrastructure layer conventions

- Every adapter implements a protocol defined in `application/`. The interface is fixed by the use case; the adapter adapts to it.
- **Inherit from the port explicitly.** An adapter must subclass the `Protocol` it implements (`class SqlAlchemyUserRepository(UserRepository):`), never rely on structural (implicit) conformance. Explicit inheritance makes the contract the adapter fulfills visible right at the class declaration.
- Use `ankibot/infra/logger.py` for all logging; follow existing patterns, no ad-hoc loggers.
- Never log secrets or sensitive payloads: bot tokens, provider API keys, and user credentials must stay out of logs, and avoid dumping raw message text or file contents. Prefer stable structured fields (e.g. `user_id`, `chat_id`, `card_id`) over baking values into free-text log messages, so logs stay searchable and safe to retain.
- Configurable adapters take their `config` dataclass argument (see Configuration below) **first** in `__init__`, before any other collaborators (clients, sessions, other adapters).

To add an adapter, prefer the `/add-adapter` skill.

## Naming

**Use-case folders and operations:**

- Name the **folder** after the use case — the actor's goal — not after one of its operations. Two patterns are fine: a capability noun for CRUD-style catalogs (`manage_cards/`, `manage_tags/`), or a goal phrase for a workflow (`review_application/`, `user_registration/`).
- Name each **operation module** by its verb+entity (`create_card.py`, `read_application.py`, `accept_application.py`), and the **interactor class** to match (`CreateCard`, `AcceptApplication`).
- Never let the folder and a module **stutter**: `issue_invite/issue_invite.py` is wrong — the folder is `manage_invites/`, the operation is `issue_invite.py`.

**Interfaces (ports):** name by role, not technology (`UserRepository`, `EmailSummarizer`, `FlashcardGenerator`, `PaymentGateway`). No `I` / `Base` / `Abstract` prefixes or suffixes.

**Implementations (adapters):** name as `<ProviderOrTechnology><InterfaceName>` (`SqlAlchemyUserRepository`, `InMemoryUserRepository`, `OpenAIFlashcardGenerator`, `AnkiConnectFlashcardGenerator`, `StripePaymentGateway`, `FakePaymentGateway`). The name must make the concrete technology, service, or environment obvious.

## Configuration

`configs/config.yaml` is the single source of truth for runtime configuration values.

- Reference environment variables with OmegaConf syntax: `${oc.env:VAR_NAME,default_value}`.
- Document non-obvious options with comments directly in `configs/config.yaml`.
- OmegaConf loads `config.yaml` into the root `Config` dataclass in `bootstrap/config.py`.
- For each configurable class, define a config dataclass in the **same module** as the class (e.g. `OpenAIEmailSummarizerConfig` next to `OpenAIEmailSummarizer`). The constructor takes a single `config` argument of that type: `def __init__(self, config: ...Config): ...`.
- **Every config dataclass is `@dataclass(frozen=True, kw_only=True)`** — immutable at runtime, constructed by name so field order isn't a positional contract.
- **Don't duplicate config values as dataclass defaults.** `config.yaml` is the single source of truth: a field that is always set there must have **no** default in the config dataclass, otherwise the two drift. Give a field a default only when it is genuinely optional and omitted from `config.yaml`.
- `bootstrap/config.py` imports every per-class config dataclass and aggregates them into the root `Config`. The bootstrap code loads `config.yaml`, instantiates `Config`, and passes the appropriate config object to each class that depends on it.
- `.env.example` lists every environment variable the bot requires, with placeholder values and no secrets — it's the checklist a developer copies to `.env`. Keep it in sync with `config.yaml`: when you add or remove an `${oc.env:VAR_NAME}` reference **without** a default, add or remove the matching key in `.env.example`.

## Code style

- Write all comments and documentation in English.
- Prefer clear names over comments; comment only non-obvious business logic or algorithms.
- Use `typing` only for constructs with no built-in generic form (`Protocol`, `TypedDict`, `Literal`, etc.).
- `ankiweb/**` (repo root, a sibling of `ankibot/`) is generated from `proto/` and is **not committed**.
  It lives outside `ankibot/` so generated modules resolve each other by the plain top-level name protoc
  always gives them (e.g. `ankiweb.common_pb2`), with no import-path juggling. Never edit the generated
  modules by hand — change the `.proto` and regenerate.

## Development workflow

Dependency management uses `uv`:

- `uv sync && make compile_proto` — first-time setup. Nothing imports until the protobuf modules are
  generated: `mypy` and `pytest` both fail on a fresh clone without it.
- `uv sync` — install/synchronize dependencies.
- `uv add <package>` / `uv add --dev <package>` — add a runtime / development dependency.
- `make compile_proto` — regenerate the protobuf modules after any change to `proto/`. `make run` and
  `make test` do this automatically; a bare `uv run pytest` does not.
- `make export_requirements` — generate `requirements.txt` for deployment.

Running and packaging:

- `make run` — run locally.
- `make build_image` — build the Docker image.
- `make run_container` — run in a container. Ensure `.env` is populated.

Quality checks — run before committing:

- `uv run mypy ankibot tests` — type-check (strict-ish; keep it clean). `tests` is not optional: the
  `@override` rule on test doubles (see Testing) is enforced by nothing else.
- `uv run codespell ankibot` — spell-check.

Skip these on read-only work or when unrelated user changes are staged and you only need a non-mutating check.

## Testing

Tests are split first by what it takes to run them, then organized by capability using the same names as the source:

- `tests/unit/` — pure Python, no transport, milliseconds. Extracted rules and domain logic, not the bot.
- `tests/integration/` — needs a simulated transport, an external process, or the composed `Dispatcher`.
  The dispatcher qualifies even though no transport runs: what it covers is the wiring in
  `bootstrap/bot.py` — router order, dependency injection by parameter name, the errors router — none of
  which a directly-called handler reaches. Handler behaviour is covered there for the same reason:
  going through the dispatcher is what puts the command filter and the injection under test.

Inside each level, group tests by the capability they cover, reusing source names (`tests/integration/bot/` for the bot as `bootstrap/bot.py` composes it — routers, handlers and injected dependencies together — `tests/integration/infra/anki/` for `infra/anki/`, `tests/unit/handlers/` for what is left of `presentation/handlers/`). Two directories must never share a name for different sources. Split at behavior granularity, not file granularity: one source module may warrant several test modules, one per operation or rule. Test-only infrastructure (`tests/common/fakes/`, fixtures, stubs) has no source counterpart and is placed where it reads best.

Do not treat this as one-test-file-per-source-file, and do not create a test module just to mirror a source module that has no behavior of its own. Interactors are covered through the handler boundary rather than by isolating each one with mocked ports.

Every test directory has an `__init__.py`; same-named test modules in different directories break collection otherwise.

### What not to test

Before writing a test, state the failure it would catch as a guarantee to the user. If the guarantee comes out as a description of the implementation, there is nothing to test. The naming rule below is the same filter: a test that does not fit `test_<actor>_<can|cannot>_<capability>` is usually a test of wiring, not of behavior.

- **Never assert on a test double.** `fake.calls == 1`, `mock.assert_called_once()` assert that wiring happened, not that anything works — and they break on refactors that change nothing for the user. **This does not cover the session recorder.** `RecordingSession` stands in for no collaborator and decides nothing: it is the observation point on the Telegram boundary, and `session.requests` holds the outgoing request itself — the same thing a proxy log would show. Asserting what we sent to Telegram is the assertion; asserting that a fake port was called is not.
- **Delegation is not behavior.** A method that forwards to a collaborator and makes no decision has nothing to assert. Test it where the decision is made.
- **Name the existing test that would fail** if this behavior broke. If one would, the new test is redundant: strengthen that test instead of adding beside it.
- **When an interactor grows a rule worth many cases**, extract the rule into a plain function and unit-test the function (see Domain model). Do not reach for fake ports to get at it.

### Rules

- **Test doubles subclass what they replace** and mark methods `@override` — a fake for a port subclasses the `Protocol`, a fake for a concrete collaborator subclasses that class. Without it a signature change leaves the double silently stale and the tests keep passing against a contract that no longer exists. This only has teeth while `explicit-override` is enabled in mypy **and** `tests` is in the paths mypy checks.
- **Substitute as deep as possible.** Prefer replacing the transport under an adapter over replacing the adapter, and the adapter over the port — the less you replace, the more real code the test exercises. Fake a port only when the layer under test sits above it.
- **Name test data builders for what they do** (`make_user`, `UserBuilder`), never after a production port — reusing a port's name for a builder makes the term mean two things.
- **Prefer fakes over patching.** Reach for `monkeypatch` / `mock.patch` only when no fake is possible; never patch private internals.
- **Never simulate the Telegram API.** Substitute at the session and assert on the outgoing method only — see The Telegram boundary below.
- **Handler tests go through the dispatcher.** Feed a real `Update` to the composed `Dispatcher` (`dispatcher.feed_update(bot, update)`) over a `Bot` whose session records instead of sending, with real interactors built over fake ports. One pass then covers the command filter, router order, aiogram's injection by parameter name and the handler body. A directly-called handler covers none of the first three, so a typo in `Command("auth")` leaves its tests green while the bot answers nothing.
- **Assert which reply came back, never merely that one did.** A mismatched dependency key raises `TypeError` inside the handler call, and the errors router answers in its place — so "the bot said something" passes with the injection broken. While a reply is a bare literal, comparing the whole string is the plainest way to name it and reads as what the user gets. Once a reply carries an interpolated value, assert the fragment carrying that value instead of rebuilding the message — rebuilding it copies the format string into the test, and the mapping is then close to earning the extraction under Tooling triggers.
- **Call a handler directly only for a branch no update can reach.** `unexpected_error_handler` on an update carrying no message is the standing example: reaching the errors router needs a handler that raises, and the bot registers none for callback queries or edited posts. Such a test goes in `tests/unit/handlers/` with a docstring saying why it is not in `tests/integration/bot/`.
- **Never hit real external services.** Adapter tests use `httpx.MockTransport` with a handler that asserts on the outgoing request. Never build a config from environment credentials — a real AnkiWeb login from a test risks the account.
- **Record a real upstream response only when a fake would encode a guess.** A `MockTransport` test proves only that the code agrees with our own reading of AnkiWeb's undocumented API — but for a small message whose misreading fails loudly, a hand-built protobuf is equivalent to a recorded one, and cheaper. Recording earns its cost when both hold: we *interpret* the response rather than relay it, and a wrong assumption would fail *silently*, producing a wrong card instead of an exception. Read `docs/contract-testing.md` first — real responses carry live tokens, session cookies and user content.
- **Never read `configs/config.yaml` in tests.** Construct the per-class config dataclass in a fixture with obviously-fake values.
- **Assert behavior through the handler boundary**, never private attributes or test doubles.
- **Cover failure paths**: every distinct exception branch and every alternative branch, not just the main scenario. Coverage is a floor, not the objective.
- **Never let a secret reach a log.** Any adapter handling credentials or tokens gets a test that runs it at DEBUG level and asserts the secret is absent from `caplog.text`.
- **Concurrency regressions are tests, not comments.** Anything touching shared mutable state (the process-wide httpx cookie jar, caches, sessions) gets a test running two operations under `asyncio.gather`. These bugs do not reproduce serially.
- **Retry/backoff must be configurable to zero.** Any retry policy takes its attempt count and backoff from the adapter's config dataclass, so tests can set the base delay to `0.0` instead of really sleeping.
- **Fixture scope**: expensive setup session-scoped, anything carrying state per-test. One exception, and
  only this one: a handler module's `Router` is a module-level singleton, so a second `include_router`
  raises `RuntimeError: Router is already attached` and the dispatcher must be built once per session —
  along with the fakes composed into it. A session-scoped fake carrying state pairs with an `autouse`
  fixture that resets it before every test; without that reset, do not widen the scope. Every handler
  test shares that one dispatcher, so each new fake composed into it needs its own reset in the same
  place — one added without a reset leaks into every test that runs after it.
- Name tests `test_<actor>_<can|cannot>_<capability>`; give each a one-line docstring stating the guarantee, and structure the body with `# Arrange` / `# Act` / `# Assert`.

### The Telegram boundary

`tests/common/telegram.py` substitutes at the **session** — the last layer before the network — so `Bot`,
`Message`, `Dispatcher` and the API method objects are all real. `RecordingSession` is a recorder, not a
Telegram simulator, and it must not grow into one. That is where doubles of the Bot API itself fail: the
double always answers "ok" while the real API rejects.

- **Assert only what we sent, never what Telegram would answer.** A test may state that `/auth` emits this
  `SendMessage` with this text. It may not state that Telegram accepts it.
- **Scripted responses are for exceptions and for reads.** When `RecordingSession` grows a response queue, use
  it to inject errors (`TelegramForbiddenError`, `TelegramRetryAfter`) and so cover *our* error-to-reply
  branches, or to answer a method the handler genuinely reads back — `getChat`, `getChatMember`,
  `edit_message_*`. To hand a result back, queue a real aiogram object (`Message(...)`,
  `ChatMemberOwner(...)`), never a hand-built dict standing in for an API response.
- **The stop signal is the kind of answer, not the count.** A handler that asks Telegram who administrates a
  chat before deciding needs that answer; four queued objects in one test are fine when each is a real aiogram
  object for a method we really call. Two things are not: **inventing the semantics of a reply** — deciding
  what the API "would" say about acceptance, formatting, limits or rejection — and a queue that reads as a
  **scripted dialogue**, alternating our sends with Telegram's turns. Either one means the scenario has turned
  into a simulation of Telegram; extract the rule it is really about and unit-test that instead.
- **Multi-step conversations are tested as logic, not as traffic.** Put FSM transitions in a plain function and
  test the function; leave one thin dispatcher test for routing.
- **An FSM flow splits into four things; only three are worth a test.** The transition rule (which state
  follows which input) is a plain function — unit-test it. A keyboard builder is worth testing only when it
  decides something: pagination, conditional buttons, and above all hand-rolled `callback_data`, whose
  64-byte limit fails only in production; a static markup is a constant. Routing and **state isolation
  between users** go through the dispatcher over a real `MemoryStorage` — a wrong storage key leaks one
  user's state into another's and no unit test sees it. The full scripted dialogue is the redundant one.
- **Fabricating input is allowed; fabricating a reply is not.** Building an `Update` — a `Message` or a
  `CallbackQuery` — assumes nothing about how the server behaves. Reading a result back does: `edit_message_*`
  returns `Message | bool`, so the moment a handler edits its own message it wants an answer we do not
  have. `RecordingSession` therefore hands back `UnreadResult`, which raises on any attempt to read it:
  an empty dict would have been *falsy* and sent the handler silently down its failure branch. That
  exception is the signal the response queue above has earned its keep, under the same rule: a real
  aiogram object for a call we really make, never an invented answer.

These tests cannot catch, and must not claim to: HTML/parse-mode errors on real content, message and keyboard
size limits, flood control, a blocked bot, or anything else the server decides. That confidence only comes from
a real run against the Bot API test environment, which is out of scope for the suite today.

### Tooling triggers

The suite is deliberately small in dependencies. Do not add any of the following preemptively — each has a concrete trigger, and adding it earlier buys nothing but setup cost:

| Tool / technique                                | Add it when                                                                                                                                                                                                                                                                                                                                                                                                                            | Not before, because                                                                                                                                                          |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `polyfactory` factories                         | an input DTO reaches ~3 fields and tests repeat its construction with one field varied                                                                                                                                                                                                                                                                                                                                                 | today's DTOs are empty or trivial; explicit construction reads better                                                                                                        |
| `hypothesis`                                    | logic covers a wide input space with a stateable invariant — spaced-repetition intervals, form validation, parsing                                                                                                                                                                                                                                                                                                                     | example-based tests are clearer for a handful of enum branches                                                                                                               |
| A `Clock` port + frozen-clock fixture           | any behavior depends on the current time. Inject `Clock` rather than calling `datetime.now()` in an interactor                                                                                                                                                                                                                                                                                                                         | nothing is time-dependent yet — but SRS scheduling makes this near-certain                                                                                                   |
| `testcontainers`                                | a real stateful dependency appears (database, cache, queue). Then run migrations once into a template database and clone it per test                                                                                                                                                                                                                                                                                                   | there is no such dependency; `httpx.MockTransport` covers the HTTP adapter better                                                                                            |
| Tests against a gateway/repository in isolation | its query grows non-trivial (batching, pagination, exclusion rules) and its contract promises something the caller cannot observe, such as "one query, not N+1"                                                                                                                                                                                                                                                                        | behavior through the handler boundary covers simpler persistence adequately                                                                                                  |
| Isolated interactor tests over fake ports       | orchestration in `execute` grows a branch no handler input can reach, or the path through the dispatcher gets expensive (a real database appears). Extracting a plain function stays the first resort — this is for decisions taken on what a port *returned*. Hand-write in-memory fakes that subclass the port, and assert on what `execute` returned, never on the fake                                                             | one stateless interactor is already covered through the dispatcher, so isolating it would test the wiring a second time and nothing else                                     |
| A pure `error → reply` mapping, unit-tested     | a handler's except-chain passes ~5 branches, or a reply grows an interpolated value. Extract the mapping to a plain function, table-test every branch there, and keep **one** dispatcher test proving the handler is wired to it. Until then the reply is the handler's only observable output — it catches nothing, and neither does "no exception was raised": `feed_update` never propagates one, the errors router answers instead | four one-line branches read faster in the handler than in a lookup table, and the dispatcher tests covering them catch a broken filter, router order and DI in the same pass |
| `pytest` markers for slow/e2e selection         | a test exceeds a couple of seconds or waits on a terminal state with a timeout                                                                                                                                                                                                                                                                                                                                                         | the whole suite runs fast enough to always run whole                                                                                                                         |
| `pytest-xdist`                                  | the full run stops being instant                                                                                                                                                                                                                                                                                                                                                                                                       | two test files parallelize into a slowdown                                                                                                                                   |

When a trigger fires, add the tool for that one case — not across the suite retroactively.

The interactor row is calibrated against a mature aiogram codebase (`bomzheg/Shvatka`, ~90 interactors over a
real database): isolated tests driven with hand-written in-memory fakes are the shape to copy when the trigger
fires. Two habits of theirs stay out — fakes that only match a port structurally instead of subclassing it,
which mypy cannot keep from drifting, and assertions on what a fake repository was asked to do.

### Commands

- `uv run pytest tests/integration/bot` — every handler through the real dispatcher; the default while
  changing a command.
- `uv run pytest tests/unit` — fast, no transport; the default while changing an extracted rule.
- `uv run pytest tests/integration/infra/anki -k invalid_password` — focused selection.
- `uv run pytest` — before committing, and whenever the change touches ports, adapters or config.
