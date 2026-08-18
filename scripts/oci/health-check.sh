#!/usr/bin/env bash
# Health check through Nginx (HTTPS). Expect database: ok.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

URL="${HEALTH_URL:-https://127.0.0.1/api/v1/health}"

echo "==> GET ${URL}"
curl -skf "$URL" | python3 -m json.tool || {
  echo "Health check failed" >&2
  exit 1
}
