# AnkiWeb Authentication — Specification

How authentication works for a programmatic client (e.g. ankibot) talking to the
AnkiWeb `/svc/*` API.

> **Source & confidence.** Reconstructed from the AnkiWeb web client (the login
> page component and the transport layer of the protobuf client). The overall
> flow, the cookie-based session model, and the cross-domain token hand-off are
> all confirmed from that code.

## Overview

AnkiWeb uses a **cookie-based session**. After a successful login the server sets
an `HttpOnly` session cookie via `Set-Cookie`, and the browser automatically
attaches it to subsequent same-origin requests. There is **no** bearer token or
`Authorization` header on API calls — the session lives entirely in the cookie.
If the cookie is missing (e.g. cookies disabled), the login flow cannot complete.

The one subtlety is that AnkiWeb spans **two domains**, and a full session
requires authenticating against both.

## The two-domain nuance

AnkiWeb is deliberately split across two origins:

- **`ankiweb.net`** — the main site: account (login, signup, settings), deck
  management, and the shared-deck / add-on catalog.
- **`ankiuser.net`** — the study interface and note editing.

**Why the split exists.** Cards can contain arbitrary author-supplied HTML/JS.
By hosting the study and editing surfaces on a separate origin, malicious card
JavaScript is isolated from the account endpoints on the main site and cannot
trigger them. This is a security boundary, not a cosmetic one.

**Consequence for auth.** A session cookie is scoped to a single domain, so the
`ankiweb.net` cookie obtained at login does **not** authorize `ankiuser.net`.
Logging in therefore produces a short-lived cross-domain token that is exchanged
for a **second** session cookie on `ankiuser.net`.

**Which domain serves which endpoints.** Account, deck-management, and shared
catalog endpoints are served from `ankiweb.net`; study and note-editing endpoints
are served from `ankiuser.net`.

## Authentication flow

1. **Entry guard.** Query the account status (`/svc/account/get-account-status`).
   If already logged in, skip straight to the app; if the server returns a
   redirect target, follow it.

1. **Log in on `ankiweb.net`.** Submit credentials to `/svc/account/login` with
   `LoginRequest { username, password }`, where `username` is the account email.
   The response is `LoginResponse { status, token }`. On success the server also
   sets the `ankiweb.net` session cookie.

1. **Branch on `status`:**

   - `AUTHENTICATED` — proceed to step 4.
   - `INVALID_USER` — no account exists for that email.
   - `INVALID_PASS` — wrong password.
   - `UNKNOWN` — unexpected server response.

1. **Exchange the token on `ankiuser.net`.** Hand the `token` from the login
   response to the token-exchange login endpoint on `ankiuser.net`:
   `GET https://ankiuser.net/account/ankiuser-login?t={token}`. This is a plain
   GET with the token as a query parameter — not a `/svc/*` protobuf POST, and
   outside the reverse-engineered client bundle `ankiweb-api.md` covers. It
   establishes the `ankiuser.net` session cookie via `Set-Cookie` on the
   response; the response body format is not load-bearing (treat any 2xx/3xx
   as success and confirm by checking that an `ankiuser.net` cookie is now
   present, not by parsing the body).

   **Do not follow the redirect.** In practice this endpoint answers with a
   `303 See Other`, and the `Set-Cookie` for the `ankiuser.net` session rides on
   that `303` response itself. The redirect target is just a landing page and is
   irrelevant to auth. A client that follows the redirect will end up inspecting
   the *final* response, whose `Set-Cookie` no longer carries the session cookie —
   so disable redirect following on this request (`follow_redirects=False`) and
   read the cookie from the `303` response directly.

1. **Make authorized calls.** From now on, send each `/svc/*` request to the
   correct domain and let the matching session cookie authorize it: `ankiweb.net`
   endpoints ride the first cookie, `ankiuser.net` endpoints ride the second.

1. **Handle expiry.** A `403` on any `/svc/*` call means the session is
   invalid/expired; re-run the login flow.

## High-level implementation steps

1. **Login** — POST to `/svc/account/login`, parse `status`, and on
   `AUTHENTICATED` capture both the `token` and the `ankiweb.net` session cookie.
1. **Token exchange** — call the `ankiuser.net` login endpoint with the `token`
   and capture the `ankiuser.net` session cookie from the `303` response
   (`follow_redirects=False` — see step 4 above).
1. **Authorized requests** — route each endpoint to its domain and send the
   matching cookie automatically (a single HTTP session with a shared cookie jar
   handles both domains).
1. **Expiry handling** — treat `403` as an expired session and re-login.
1. **Session persistence** — persist the cookies between runs so the bot doesn't
   log in on every start.
1. **Secrets** — keep the email/password out of source (config or secret store),
   and keep the password out of logs.

## Acceptance criteria

- Valid credentials return `AUTHENTICATED`, and a subsequent `ankiweb.net` call
  (e.g. deck list) succeeds without a `403`.
- After the token exchange, an `ankiuser.net` call succeeds without a `403`.
- `INVALID_USER` / `INVALID_PASS` surface as distinct, non-fatal errors.
- An expired/missing session (`403`) triggers a clean re-login rather than a
  hard failure.
- The password never appears in logs.
