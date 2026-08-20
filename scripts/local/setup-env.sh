#!/usr/bin/env bash
# Create .env from .env.local.example with generated secrets (idempotent if .env exists).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  echo ".env already exists — leaving it unchanged."
  echo "Edit CORS_ORIGINS / FRONTEND_URL / BACKEND_URL as needed."
  exit 0
fi

if [[ ! -f .env.local.example ]]; then
  echo "Missing .env.local.example" >&2
  exit 1
fi

cp .env.local.example .env

# Generate secrets without requiring openssl (python always available in this stack's host tooling often).
python3 - <<'PY'
import pathlib
import re
import secrets

path = pathlib.Path(".env")
text = path.read_text(encoding="utf-8")

def set_key(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    return content + ("\n" if not content.endswith("\n") else "") + line + "\n"

pg = secrets.token_urlsafe(24)
jwt = secrets.token_urlsafe(32)
admin = secrets.token_urlsafe(18)

text = set_key(text, "POSTGRES_PASSWORD", pg)
text = set_key(text, "JWT_SECRET", jwt)
text = set_key(text, "ADMIN_SECRET", admin)
# Local-first defaults until share.sh / LAN IP is applied
text = set_key(text, "CORS_ORIGINS", "http://localhost,http://127.0.0.1")
text = set_key(text, "FRONTEND_URL", "http://localhost")
text = set_key(text, "BACKEND_URL", "http://localhost")
path.write_text(text, encoding="utf-8")
print("Created .env with generated POSTGRES_PASSWORD, JWT_SECRET, ADMIN_SECRET.")
print(f"ADMIN_SECRET={admin}")
print("Save the admin secret — you need it for /admin.")
PY
