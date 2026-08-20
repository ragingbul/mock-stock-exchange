#!/usr/bin/env bash
# Write a public base URL (ngrok / LAN) into .env and restart backend + nginx.
# Usage: ./scripts/local/apply-public-url.sh https://abc123.ngrok-free.dev

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PUBLIC_URL="${1:-}"
if [[ -z "$PUBLIC_URL" ]]; then
  echo "Usage: $0 https://YOUR-ID.ngrok-free.dev" >&2
  exit 1
fi

# Strip trailing slash
PUBLIC_URL="${PUBLIC_URL%/}"

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

python3 - "$PUBLIC_URL" <<'PY'
import pathlib
import re
import sys

public = sys.argv[1].rstrip("/")
path = pathlib.Path(".env")
text = path.read_text(encoding="utf-8")

def set_key(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    if not content.endswith("\n"):
        content += "\n"
    return content + line + "\n"

# Keep local origins + public URL (dedupe, preserve order)
base_origins = ["http://localhost", "http://127.0.0.1"]
existing = []
m = re.search(r"^CORS_ORIGINS=(.*)$", text, re.MULTILINE)
if m:
    existing = [o.strip() for o in m.group(1).split(",") if o.strip()]

origins = []
for o in base_origins + existing + [public]:
    if o not in origins:
        origins.append(o)
# Drop stale ngrok hosts if public is ngrok (optional cleanup of other ngrok URLs)
if "ngrok" in public:
    origins = [
        o for o in origins
        if o == public or "ngrok" not in o
    ]
    if public not in origins:
        origins.append(public)

text = set_key(text, "CORS_ORIGINS", ",".join(origins))
text = set_key(text, "FRONTEND_URL", public)
text = set_key(text, "BACKEND_URL", public)
path.write_text(text, encoding="utf-8")
print(f"Updated .env CORS / FRONTEND_URL / BACKEND_URL → {public}")
PY

COMPOSE="docker compose -f docker-compose.local.yml"
if ! command -v docker >/dev/null 2>&1; then
  echo "Updated .env, but docker was not found — start Docker Desktop, then run:" >&2
  echo "  docker compose -f docker-compose.local.yml restart backend nginx" >&2
  exit 0
fi

echo "==> Restart backend + nginx (pick up new CORS / URLs)"
$COMPOSE up -d nginx >/dev/null
$COMPOSE restart backend nginx

echo "Done. Leave NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL empty (same-origin)."
