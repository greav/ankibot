# Recording Real AnkiWeb Responses

When a hand-built payload is enough, and when it quietly encodes a guess — the criterion and the
traps, written down so the decision does not have to be re-derived when the next endpoint arrives.

Read `ankiweb-api.md` for the endpoints and `ankiweb-auth.md` for the two-domain cookie flow.

## The gap a recording closes

Adapter tests drive the adapter through `httpx.MockTransport`. The handler in those tests is
written by us, from our own reading of the protocol, so they prove one thing only: **the code
agrees with our assumptions about AnkiWeb**. They cannot disagree with those assumptions.

AnkiWeb's API is undocumented and reverse-engineered, so the assumptions can simply be wrong. A
recording removes us from one side of the loop: it feeds bytes AnkiWeb actually sent into the
production parser.

That is a **one-time check of our reading**, not an ongoing guard — see Limits below.

## The criterion

Recording earns its cost when **both** hold:

1. we **interpret** the response rather than relay it — meaning is extracted from it and ends up in
   what the user sees;
1. a wrong assumption fails **silently** — a wrong card rather than an exception.

When either is false, a hand-built protobuf is equivalent to a recorded one and far cheaper: the
same production parser, the same bytes-in shape, none of the credential handling below.

**Login did not qualify.** `LoginRequest`/`LoginResponse` are two messages, four fields and a
four-value enum — there is nothing to misread. And every failure is loud: HTML instead of protobuf
raises, a renamed field leaves `token` empty and raises, a moved endpoint returns non-200 and
raises. `test_anki_web_authenticator.py` covers all of it with fakes.

**Collections and notes will.** `ankiweb-svc.reference.proto` already shows the shape of that work —
`DeckTreeNode` is recursive, `Notetype`, `SchedulingState` and `FsrsMemoryState` are nested. Which
fields are actually populated, what arrives empty versus absent, what units timestamps use, how a
nested or filtered deck is represented: none of that can be invented, and getting it wrong produces
a wrong flashcard, not a stack trace.

## Limits

A recording is a snapshot. Replaying it re-verifies the parser against **what AnkiWeb looked like
when we recorded**; it asks AnkiWeb nothing today. Drift surfaces only on re-recording, so the
workflow is *re-record, then run* — never *run and learn something new*. Detecting drift
automatically would need a scheduled job against the live service: real credentials in CI and a
flaky suite, deliberately out of scope.

Note also where the value sits. Confirming our reading happens **at the moment of looking** at what
came back; committing the payload afterwards buys only a diff baseline for the next re-recording
and a documented sample of reality. Recording without committing is a legitimate outcome, and it
removes every risk in the next section.

## Traps, for whoever writes the next recorder

A real response is a credential: the login response carries a **live exchange token**, the
responses around it carry **`Set-Cookie` headers with real session cookies**. Collection responses
add a second problem — they carry **user content**: real notes, real deck names.

Committing any of that publishes it, and it goes wrong quietly.

- Scrub **before writing**, never after — nothing secret should reach disk or stdout at all.
- Protobuf bodies are binary: scrub by re-serializing the parsed message with the sensitive fields
  replaced, not by editing bytes.
- Replace each value with an obviously-fake constant **of the same shape**, and leave a header
  AnkiWeb did not send absent — the recorded response has to keep the shape the adapter branches on.
- Verify **before the first `git add`**: a scrubbed file whose unscrubbed predecessor is already in
  history is still a leak.
- Record against a throwaway AnkiWeb account, not the real one. Deliberately failing logins is what
  triggers rate limiting and lockouts.

## Related deferred item: retry policy must be testable

There is no retry logic in the AnkiWeb adapter yet. When one is added, its attempt count and backoff
delays must come from the adapter's config dataclass rather than being constants in the code — so a
test can set the base delay to `0.0` and exercise the retry branches without actually sleeping.

Deciding this at the moment the retry is written costs nothing. Retrofitting it later means either
slow tests or a refactor.
