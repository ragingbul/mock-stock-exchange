#!/usr/bin/env bash
# Health check via nginx on port 80.

set -euo pipefail

URL="${HEALTH_URL:-http://127.0.0.1/api/v1/health}"
echo "==> GET $URL"
curl -sf "$URL" | python3 -m json.tool 2>/dev/null || curl -sf "$URL"
