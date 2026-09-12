# Deployment

The bot runs on a plain VPS as a Docker container, in a **pull model**: on every push to
`master`, `.github/workflows/deploy.yml` runs the quality checks, builds the image and
pushes it to GitHub Container Registry (`ghcr.io/greav/ankibot`) — and stops there. The
server polls on its own: a systemd timer fetches the current `deploy/compose.yaml` from the
repository, pulls the image and restarts the container if either changed.

Nothing outside the server can reach into it. No SSH key, host, or token for the server
exists in GitHub; the pipeline's only power is to publish an image. The server holds
`/opt/ankibot/{compose.yaml, .env, deploy.sh}` plus two systemd units — `.env` is the one
file that is genuinely the server's own; everything else is a copy of what is in git. While
the repository is private the server also holds two read-only tokens (repository contents,
ghcr pulls); both go away when it becomes public.

`configs/config.yaml` ships inside the image, so changing it is a normal commit to
`master` — reviewed, tested and rolled back together with the code. A value that must
change without a redeploy belongs in `.env` instead: give it an `${oc.env:VAR,default}`
reference in `config.yaml` first.

## One-time server setup

All commands run on the server as root (or with `sudo`) unless stated otherwise.

1. **Install Docker** (includes the compose plugin):

   ```sh
   curl -fsSL https://get.docker.com | sh
   ```

1. **Create a deploy user** and let it drive Docker:

   ```sh
   useradd -m -s /bin/bash deploy
   usermod -aG docker deploy
   ```

   Membership in the `docker` group is root-equivalent on the host — use a dedicated user,
   not your interactive account. Nothing logs in as `deploy` over SSH: it exists only to
   own `/opt/ankibot` and to run the timer.

1. **Lay out the app directory.** The server has no clone of the repository, so the files
   travel from your machine. From the repository root on your machine:

   ```sh
   scp deploy/deploy.sh deploy/systemd/ankibot-deploy.{service,timer} .env.example <you>@<host>:/tmp/
   ```

   On the server, create the directory as root, then do the rest in one session **as
   `deploy`** — the files are then his from the start, which is what the timer needs:

   ```sh
   install -d -o deploy -g deploy /opt/ankibot
   sudo -iu deploy
   ```

   ```sh
   cp /tmp/deploy.sh /opt/ankibot/                      # arrives executable; git tracks the bit
   install -m 600 /tmp/.env.example /opt/ankibot/.env
   vim /opt/ankibot/.env                                 # fill in the real values, delete CONFIG_PATH

   # while the repository is private — see the notes below for both tokens:
   touch /opt/ankibot/github.token && chmod 600 /opt/ankibot/github.token
   vim /opt/ankibot/github.token                         # one line: the fine-grained token
   docker login ghcr.io -u greav                         # paste the classic token at the password prompt

   exit
   ```

   - `deploy.sh` is what the timer runs; it changes rarely — re-copy it by hand when it does.

   - In `.env`, delete the `CONFIG_PATH` line: it is for local runs, and `env_file` values
     override the path the image sets for itself.

   - `github.token` lets `deploy.sh` fetch `compose.yaml` from a private repository: a
     **fine-grained** personal access token (GitHub → Settings → Developer settings →
     Fine-grained tokens), repository access limited to `ankibot`, permission *Contents:
     read-only*, nothing else.

   - `docker login` lets `deploy` pull the private ghcr package. ghcr accepts only a
     **classic** token (`ghp_…`): GitHub → Settings → Developer settings → Personal access
     tokens → **Tokens (classic)**, single scope `read:packages`. The fine-grained kind
     (`github_pat_…`, the UI's default) is not accepted by ghcr — that is what
     `denied: denied` at login means. Docker stores the token in `~deploy/.docker/config.json`.

   - Name both tokens after where they live and what they do (`ankibot-vps repo read`,
     `ankibot-vps ghcr pull`) and give them an expiry: they are temporary by design. Once
     the repository goes public, make the package public too (GitHub → Packages → `ankibot`
     → Package settings → Change visibility), then delete `github.token`,
     `sudo -iu deploy docker logout ghcr.io`, and revoke both — `deploy.sh` fetches
     anonymously from then on, no change needed. The image carries no secrets —
     `config.yaml` reads every sensitive value from `.env`.

   `compose.yaml` needs no copying — `deploy.sh` fetches it from `master` on every run.

1. **Install the timer.** The image must exist first: push to `master` (or run the workflow
   from the Actions tab) and wait for it to go green — that creates the `ankibot` package in
   ghcr. Then, as root (the unit files arrived in `/tmp` with step 3):

   ```sh
   cp /tmp/ankibot-deploy.{service,timer} /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now ankibot-deploy.timer
   ```

   `--now` starts the timer, and since `OnBootSec=2min` is long past on a running server,
   the first `deploy.sh` run happens right away — this *is* the first deploy. After that the
   timer ticks every two minutes after the previous run. A tick is one request to GitHub and
   one to ghcr; nothing else happens unless the compose file or the image digest changed.

1. **Check the first deploy:**

   ```sh
   systemctl status ankibot-deploy.service  # result of the run that --now triggered
   journalctl -u ankibot-deploy -n 50       # what the run did
   docker compose -p ankibot logs -f        # the bot itself
   ```

   To run a deploy by hand at any time, outside the schedule:

   ```sh
   systemctl start ankibot-deploy.service   # blocks until done, exits non-zero on failure
   ```

## Repository secrets

None. `GITHUB_TOKEN` is provided by Actions automatically and pushing to ghcr needs no
extra secret. There is nothing to configure under Settings → Secrets.

## Day-to-day

- **Deploy** — merge/push to `master`; the workflow publishes the image and the server
  picks it up within a couple of minutes. A green run in Actions means "image published",
  not "bot restarted": the applying side is `journalctl -u ankibot-deploy`.

- **Logs** — `docker compose -p ankibot logs -f` from any user in the `docker` group
  (rotated at 3 × 10 MB). Deploy runs: `journalctl -u ankibot-deploy -f`.

- **State** — `/opt/ankibot/data/` is the bot's persistent state (today: each user's
  `/decks` and `/model` choices in `user_preferences.json`), bind-mounted into the
  container by `compose.yaml`. Docker creates the directory on first start. Besides `.env`,
  it is the one thing on the host worth keeping across a reinstall; a corrupt file there
  stops the bot on launch rather than sending cards to the wrong deck. The older
  `selected_decks.json` is not read: after the deploy that introduced `/model`, each user
  picks their deck once more through `/decks`.

- **Config change** — commit to `configs/config.yaml` (or `deploy/compose.yaml`) and push
  to `master`; both deploy like any code change. Only `.env` values are changed on the
  server: edit the file, then `docker compose -p ankibot up -d --force-recreate`.

- **Rollback** — the normal way is `git revert` on `master`: the pipeline builds the
  reverted code and the timer applies it. For an emergency pin, stop the timer first,
  otherwise the next tick puts `:latest` back. Only the newest 10 builds stay in ghcr
  (the `retain` job deletes older ones), so a pin can reach back 10 master commits:

  ```sh
  systemctl stop ankibot-deploy.timer
  # edit /opt/ankibot/compose.yaml to image: ghcr.io/greav/ankibot:<sha> (every build is
  # also tagged with its commit SHA), then:
  docker compose -p ankibot up -d
  # ... fix master, let it build, then resume polling:
  systemctl start ankibot-deploy.timer
  ```

## Working as yourself, not as `deploy`

Nothing logs in as `deploy` — it has no password and no SSH key. Everything is done from
your own account with `sudo`; the only rule is to keep the files in `/opt/ankibot` owned by
`deploy`, because the timer reads them as `deploy` and a root-owned `.env` (mode 600) would
fail the next tick with a permission error.

- **Files in `/opt/ankibot`** (`.env`, `deploy.sh`, the emergency override) — edit as
  `deploy`, which preserves ownership:

  ```sh
  sudoedit -u deploy /opt/ankibot/.env     # or: sudo -u deploy vim /opt/ankibot/.env
  sudo -iu deploy                          # a full login shell as deploy, exit to return
  ```

  Plain `sudo vim` can leave the file owned by root: some editors save by writing a new
  file and renaming it.

- **Units in `/etc/systemd/system`** — root-owned regardless of `deploy`; edit and manage
  them with your own `sudo` (`sudo systemctl daemon-reload`, `sudo systemctl start ankibot-deploy`).

- **Read-only things need nothing**: `docker compose -p ankibot logs -f` works for any
  member of the `docker` group, `systemctl list-timers` for anyone;
  `journalctl -u ankibot-deploy` may need `sudo` for the newest entries.

## Emergency config override

The config lives inside the image, so the normal way to change it is a commit. When a bad
value must be fixed *now* — faster than a pipeline run — mount a corrected copy over the
baked-in file, as `deploy`:

```sh
cd /opt/ankibot

# 1. Extract the current config and fix the bad value
docker compose exec ankibot cat /opt/configs/config.yaml > config.yaml
vim config.yaml

# 2. Mount it over the baked-in file via a compose override
cat > compose.override.yaml <<'EOT'
services:
  ankibot:
    volumes:
      - ./config.yaml:/opt/configs/config.yaml:ro
EOT
docker compose up -d
```

Compose picks up `compose.override.yaml` automatically — including on every timer tick,
which runs `docker compose up -d` in this directory (`deploy.sh` replaces only
`compose.yaml`, never the override). That is the trap: while the override exists, it
silently shadows the config baked into every new image. The fix is not done until the
fire is out **in git**:

1. commit the real fix to `configs/config.yaml`, push, let the pipeline and the timer
   deploy it;

1. remove the hatch:

   ```sh
   rm compose.override.yaml config.yaml
   docker compose up -d --force-recreate
   ```

An extra file in `/opt/ankibot` is the visible sign a hotfix is in effect; never fold the
mount into `compose.yaml` itself — the next tick would overwrite it anyway, which is one
more reason the override file is the right place.
