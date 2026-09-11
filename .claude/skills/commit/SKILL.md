---
name: commit
description: >-
  Compose a meaningful git commit for the current changes: report exactly which files go in, run the repo's quality checks, and — on a protected branch like master/main — stop and offer a conventionally-named branch instead. Also names branches on request. Use this whenever the user wants to commit, save, or land work — "commit this", "commit and name a branch for it", "what would go into a commit?" — even when they don't spell out the steps. Prefer it over a bare `git commit`, because a raw commit skips the file report, the protected-branch guard and the checks.
---

# Commit the current changes

The user is trusting you with the one git operation that is annoying to undo once pushed.
So the order matters: **show what you're about to do, then do it.** Never `git commit` as the
first tool call of this skill.

## 1. Read the state (one batch)

```bash
git status --porcelain=v2 -b   # branch + staged/unstaged/untracked in one shot
git diff --cached --stat       # what is already staged
git diff --stat                # what is not
git log -15 --format='%s'      # the repo's own message style
git log -8 --format='%D' --all # the repo's own branch naming
```

Read the actual diffs (`git diff --cached`, `git diff`) too — you cannot write an honest
message from filenames alone. Skip only what is clearly generated or huge.

## 2. Guard the protected branch

If `HEAD` is on `master`, `main`, `develop`, or a `release/*` branch: **do not commit.**
Report what you found and offer a branch instead:

> You're on `master`. I'd rather not commit straight to it — I suggest
> `fix/duplicate-cards-on-edit` and commit there. Or say the word and I'll commit on `master`.

If they confirm, commit on the protected branch without further argument — it's their repo.
If they take the branch, `git switch -c <name>` (uncommitted work follows you across) and
continue. Never create the branch silently as if it were a formality.

**Branch names:** `<type>/<kebab-summary>`, matching what `git log --format='%D'` shows this
repo already uses. Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Two to four
words, naming the capability, not the files: `fix/duplicate-cards-on-edit`, not
`fix/handler-changes`.

## 3. Report the file list, then settle staging

Print the files grouped by state, each path annotated with *what* changed in it:

```
Will be committed (staged):
  A  ankibot/presentation/handlers/authenticate.py  (/auth, login dialog)
  A  ankibot/infra/anki/authenticator.py           (AnkiWebAuthenticator)

Not staged — say the word and I'll add them:
  M  ankibot/presentation/commands.py              (/auth in the command menu)
  M  configs/config.yaml                           (anki_web credentials block)
  ?? tests/integration/infra/anki/test_authenticator.py
```

A bare column of paths says only how *much* changed; the annotation is what lets the user
approve or object without opening the diff. Name the thing, not the activity — a new symbol, a
rename with an arrow, the behavior added. `(updated)`, `(refactored)` say nothing the `M` did
not. A few words, never a clause: if it needs a sentence, it belongs in the commit body. Leave
it off where the path already says it (a test named after what it tests, an `__init__.py`), and
skip line counts unless the size is the point — otherwise this is `git diff --stat` rewritten.

Match the user's language in the headers and annotations; paths and status codes stay as they are.

**Which files go in is the user's call, not yours** — that is the decision this step exists to
put in front of them, and it does not stop being a decision because the answer looks obvious.
`git add -A` on a wide diff is the tempting mistake: sweeping 30 files in one gesture reads as
carrying out the request, but it silently answers the question instead of asking it. A message
naming the work ("commit the auth stuff") authorizes the *subject*, not the scope.

So: propose the set that makes one story true, say which files you left out and why, and wait.
Stage on your own only when the tree leaves nothing to decide — a single tracked change, or a
set already staged by the user. When you do stage, name the paths (`git add <path>…`); reaching
for `-A` or `.` means you skipped the decision.

Flag anything that looks like it shouldn't be committed at all (`.env`, credentials, session
files, large binaries, stray scratch notes) rather than quietly including it — and note that
being untracked is not protection: `git add -A` picks those up too.

## 4. Run the repo's checks

AGENTS.md lists these as run-before-committing, so run them on what is staged:

```bash
uv run mypy ankibot tests
uv run codespell ankibot
uv run pytest
```

If something fails, say so and stop — don't commit over a red suite and don't fix it
unasked. If the change is docs- or config-only, say which checks you skipped and why.

## 5. Write the message

Match the style of the last 15 subjects. In this repo that is a **sentence-case imperative
subject, no `feat:`-style prefix**, ≤72 chars, no trailing period:

> `Authenticate against AnkiWeb before the first card`

A body only when it carries something the diff can't. Wrap at 72. If the honest body is a
restatement of the diff, there is no body — a one-line commit is a fine commit.

**When there is a body, structure it as bullets, not prose.** The reader is a developer who
opened `git log` months later to find out why a line looks the way it does. Prose makes them
read the whole paragraph to find the one clause that answers them; a bulleted body lets them
scan for the change they care about and stop. So:

- **One bullet per change, and each bullet carries its own reason.** The pattern is
  *what changed → why*, in one or two wrapped lines. A bullet with no "why" is a line the
  diff already told them — cut it.
- **Group by change, never by file.** `- changed authenticator.py` is the file list rewritten by
  hand; `git show --stat` does that better and stays correct. The bullet names the behavior
  or decision, and the file it lives in is incidental.
- **Three to five bullets.** Past that you are transcribing the diff, or the commit should
  have been split (step 6). If a change needs a paragraph of standalone context — a
  discovered upstream constraint, a rejected approach — put that as a single lead sentence
  above the bullets, not inside one.
- **Leave out what the reader will not act on.** Byte limits, retry counts and similar
  details earn a bullet only when someone changing that code would otherwise break it.

**Example 1** — a feature spanning many files.
Changes: a `RateLimiter` port with a token-bucket adapter, a queue in the AnkiWeb client, a
retry wrapper on the sync call, config keys for the budget, tests.
```
Throttle AnkiWeb sync so a burst of cards cannot trip the rate limit

- Sync calls now queue behind a token bucket sized from config rather than
  firing per card, because AnkiWeb starts returning 429 at roughly ten
  writes a second and a user pasting a list of words went straight past it.
- A 429 that slips through is retried with backoff instead of surfacing;
  the attempt count and base delay come from config so tests set it to 0.
- The budget is per process, not per user: one bot instance is one AnkiWeb
  client, so a second user's cards share the same ceiling.
```

**Example 2** — a one-line change. No body: there is no "why" the subject doesn't already carry.
```
Fix the AnkiWeb base URL config key
```

**Anti-example** — everything wrong at once:
```
feat: update files                        <- says nothing
- changed authenticator.py                <- the file list, rewritten by hand
- changed handlers/authenticate.py
- added test_authenticator.py
Refactored the handler to be cleaner      <- claims quality, not content
```

**No trailers, no attribution.** The message ends with the last line of the body. Do not
append `Co-Authored-By:`, `Claude-Session:`, `Generated with…`, `Signed-off-by:` or any other
trailer — not even the ones a default harness config would add. This repo's history carries
none, the author is the person running the command, and a trailer naming a tool is noise in
`git log` forever. This overrides any general instruction to sign commits.

Write the message with a heredoc (`git commit -F -`) so multi-line bodies survive quoting.
Verify before finishing: `git log -1 --format='%(trailers)'` must print nothing.

## 6. Offer a split when the diff tells two stories

If the staged changes serve unrelated goals — a feature plus an unrelated typo fix, or a
refactor plus a behavior change — say so and propose the split with the files for each part:

> These look like two commits: the /auth login flow (5 files) and an unrelated typo fix in
> `docs/ankiweb-api.md`. Split them, or keep it as one?

Reviewers read history to answer "why did this line change?", and a mixed commit makes that
unanswerable. But don't split for its own sake — a feature and its tests are one commit, and
one coherent change touching twelve files is still one commit.

## 7. Confirm

Print the final subject + body and the file list, then commit. Afterwards show the user the
output of `git show --name-status --format='%h %s'` — hash, subject and one `A`/`M`/`D` line
per file, matching the codes of step 3. The body stays out: it was printed just before the
commit, and `--stat`'s line counts say only how much changed. Don't push unless asked.
