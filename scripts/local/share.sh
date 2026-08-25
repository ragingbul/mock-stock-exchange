#!/usr/bin/env bash
# Expose the local TRADEVERSE stack (nginx :80) via ngrok and wire CORS/.env.
#
# Prerequisites: Docker stack running (scripts/local/start.sh), ngrok installed + authed.
# Usage: ./scripts/local/share.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.local.yml"
NGROK_API="${NGROK_API:-http://127.0.0.1:4040/api/tunnels}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/v1/health}"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.local.example to .env first (or run scripts/local/setup-env.sh)." >&2
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok not found on PATH. Install from https://ngrok.com/download and run: ngrok config add-authtoken <token>" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

echo "==> Check local stack health"
if ! curl -sf "$HEALTH_URL" >/dev/null; then
  echo "Local stack is not healthy at $HEALTH_URL" >&2
  echo "Start it first: ./scripts/local/start.sh" >&2
  exit 1
fi

get_public_url() {
  curl -sf "$NGROK_API" 2>/dev/null | python3 -c '
import json, sys
data = json.load(sys.stdin)
for t in data.get("tunnels", []):
    url = t.get("public_url") or ""
    if url.startswith("https://"):
        print(url)
        raise SystemExit(0)
for t in data.get("tunnels", []):
    url = t.get("public_url") or ""
    if url.startswith("http://"):
        print(url)
        raise SystemExit(0)
' 2>/dev/null || true
}

PUBLIC_URL="$(get_public_url || true)"
if [[ -z "${PUBLIC_URL}" ]]; then
  echo "==> Starting ngrok http 80 (logs: /tmp/tradeverse-ngrok.log)"
  # shellcheck disable=SC2086
  nohup ngrok http 80 --log=stdout >/tmp/tradeverse-ngrok.log 2>&1 &
  echo $! >/tmp/tradeverse-ngrok.pid
  for _ in $(seq 1 30); do
    sleep 1
    PUBLIC_URL="$(get_public_url || true)"
    if [[ -n "${PUBLIC_URL}" ]]; then
      break
    fi
  done
fi

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "Could not get ngrok public URL from $NGROK_API" >&2
  echo "Try manually: ngrok http 80" >&2
  echo "Then: ./scripts/local/apply-public-url.sh https://YOUR-ID.ngrok-free.dev" >&2
  exit 1
fi

echo "==> ngrok public URL: $PUBLIC_URL"
./scripts/local/apply-public-url.sh "$PUBLIC_URL"

echo ""
echo "Share these links:"
echo "  Terminal:  ${PUBLIC_URL}/terminal"
echo "  Admin:     ${PUBLIC_URL}/admin"
echo "  Screen:    ${PUBLIC_URL}/market-screen"
echo "  Health:    ${PUBLIC_URL}/api/v1/health"
echo ""
echo "Keep this machine awake. Stop tunnel: kill \$(cat /tmp/tradeverse-ngrok.pid)  (if started by this script)"
echo "Stop stack:  ./scripts/local/stop.sh"
