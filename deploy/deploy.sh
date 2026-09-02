#!/usr/bin/env bash
# Pull-model deploy step, run by ankibot-deploy.timer (see deploy/systemd/ and
# docs/deploy.md). Nothing calls into this server: it fetches the compose file from the
# repository and the image from ghcr on its own, so no credentials for the server exist
# anywhere outside it. Lives at /opt/ankibot/deploy.sh; re-copy by hand when it changes.
set -euo pipefail
cd /opt/ankibot

COMPOSE_URL="https://raw.githubusercontent.com/greav/ankibot/master/deploy/compose.yaml"
# While the repository is private, raw.githubusercontent.com needs a token: a fine-grained
# PAT with read-only access to this repository's contents, stored here with mode 600.
# Once the repository is public, delete the file — the script then fetches anonymously.
GITHUB_TOKEN_FILE=/opt/ankibot/github.token

curl_args=(-fsSL --max-time 30)
if [ -r "$GITHUB_TOKEN_FILE" ]; then
  curl_args+=(-H "Authorization: token $(<"$GITHUB_TOKEN_FILE")")
fi

tmp=$(mktemp compose.yaml.XXXXXX)
trap 'rm -f "$tmp"' EXIT
curl "${curl_args[@]}" -o "$tmp" "$COMPOSE_URL"
[ -s "$tmp" ] || { echo "refusing empty compose.yaml from $COMPOSE_URL" >&2; exit 1; }
# Refuse a file compose cannot parse instead of replacing the live one with it.
docker compose -f "$tmp" config -q
mv "$tmp" compose.yaml

docker compose pull --quiet
docker compose up -d
docker image prune -f
