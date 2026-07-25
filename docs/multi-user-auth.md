# Multi-User Authentication — Migration Notes

Design notes for moving from the current **single hard-coded AnkiWeb account** (credentials in config, one shared session) to **per-Telegram-user authentication**, where every user logs in with their own AnkiWeb credentials and manages their own decks and cards.

This is a design guide, not a step-by-step. It deliberately stays at the level of principles and traps rather than concrete class names, file paths, or signatures — those drift as the code evolves. It records the non-obvious decisions so the migration doesn't reintroduce bugs we already reasoned through. Read `ankiweb-auth.md` first for the cookie / two-domain model this builds on.

## The one trap that drives everything: sessions must be isolated per user

Cookies route **by domain, not by user**. Every user hits the same `ankiweb.net` / `ankiuser.net`. So a single shared, stateful cookie jar (such as the jar of a shared HTTP client) **cannot** work multi-user: one user's request would pick up whatever session cookie is sitting in the shared jar — possibly another user's. That is a cross-user **session leak** — both a correctness bug and a security hole.

**Consequence:** each user's session must be the explicit source of truth, applied **per request**, never carried implicitly by a shared client jar.

- A session (the cookies) lives per user in a session store, keyed by Telegram user id.
- Each authorized request attaches that user's cookies explicitly, instead of relying on the client to remember them.
- Do not try to patch a shared jar per request (clearing before/after, letting it accumulate `Set-Cookie`) — it races under concurrency. Keep the shared client's jar permanently empty (e.g. a cookie policy that stores nothing) so there is nothing to leak.

## What changes, by concern

### Credentials become runtime input, not config

Today a single account is read from config. Multi-user makes credentials a per-user runtime input: the authenticate step receives the user's credentials instead of reading a global account, and there is no global account to log in at startup — authentication is per-user and on demand.

### Session storage becomes per-user and durable

The session store is keyed by user id (save / load per user). An in-memory map is fine for development, but production wants a durable per-user store (e.g. Redis) so users don't re-authenticate on every restart. See "Persistence".

### User identity threads through every operation

Every card operation now needs to know *whose* session to use: handlers derive the Telegram user id and pass it inward; each use case carries it, loads that user's session, and authorizes with it. Keep the card **ports free of the session concept** — hide "load the session, attach cookies, refresh on expiry" inside the Anki infra adapter, so application use cases stay clean.

### HTTP client strategy

A shared HTTP client bundles two concerns — a **connection pool** (worth sharing across all users) and a **cookie jar** (must not be shared across users). Split them:

- Keep **one shared client** for its connection pool, but keep its jar empty so it never holds session state; operations attach each user's cookies per request. Avoid a client-per-user (per-user pools don't scale) and a fresh-client-per-operation (loses pooling).
- **Authentication needs to *capture* `Set-Cookie`**, so run it where captured cookies won't pollute the shared jar — a throwaway client, or read the cookies straight off the auth responses. (This dovetails with reading the token-exchange cookie off its `303` response — see `ankiweb-auth.md`.)

### Expiry is now per-user

A `403` means **that user's** session expired. Since passwords are not stored, we can't silently re-login — prompt that user to authenticate again. Keep this "detect expiry → invalidate → ask to re-auth" logic in the Anki infra adapter, scoped per user.

## Security

Handling other people's AnkiWeb passwords raises the stakes:

- **Collect credentials interactively** (a multi-step dialog), which needs conversation state.
- **Delete the password message immediately**, never echo it, never log it (the existing "no secrets in logs" rule already applies).
- **Do not store passwords.** Persist only the session cookies; on expiry, ask the user to re-authenticate. Long-term storage of AnkiWeb passwords is a liability we avoid entirely.
- **Cookies are session credentials** — encrypt them at rest (or keep the store in a closed perimeter) and give them a TTL.

## Persistence

A durable store persists bytes; requests need live cookies. Bridge that gap at the infra boundary, leaving the application and the session-store contract unaware of the storage format.

- **Persist the plain cookie fields** (name, value, domain, path, expiry, secure) as data — do not serialize the HTTP-client cookie object itself (fragile across library versions, unsafe to deserialize).
- Convert at the Anki infra boundary: session cookies → plain data on save, plain data → live cookies before a request. Prefer a transport-agnostic session representation so no HTTP-client type leaks into the application layer.
- Use the store's **TTL** to match session lifetime — expired sessions self-evict, and a missing session naturally triggers a re-auth prompt.

## Checklist

- [ ] Credentials as per-user runtime input; no global account, no startup auto-auth.
- [ ] Per-user, durable session store (with TTL + encryption).
- [ ] Shared client with an empty jar; per-request cookies; auth captured off a throwaway client / the responses.
- [ ] User id threaded through handlers and every use case; card ports stay session-agnostic.
- [ ] Per-user expiry handling → re-auth prompt.
- [ ] Interactive credential dialog; delete the password message; never store passwords.
