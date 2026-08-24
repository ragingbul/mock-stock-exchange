#!/usr/bin/env bash
# Post-deploy verification: health, optional load test.
#
# Usage:
#   ./scripts/oci/verify-deployment.sh
#   HEALTH_URL=https://203-0-113-10.sslip.io ./scripts/oci/verify-deployment.sh --load-test

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

LOAD_TEST=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --load-test) LOAD_TEST=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Derive base URL from .env if HEALTH_URL not set
if [[ -z "${HEALTH_URL:-}" ]]; then
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    source .env
    BASE="${FRONTEND_URL:-${NEXT_PUBLIC_API_URL:-https://127.0.0.1}}"
    HEALTH_URL="${BASE}/api/v1/health"
  else
    HEALTH_URL="https://127.0.0.1/api/v1/health"
  fi
fi

BASE_URL="${HEALTH_URL%/api/v1/health}"

echo "==> Health check: ${HEALTH_URL}"
if ! curl -skf "$HEALTH_URL" | python3 -m json.tool; then
  echo "Health check failed" >&2
  exit 1
fi

echo ""
echo "==> UI endpoints"
echo "  Terminal:      ${BASE_URL}/terminal"
echo "  Admin:         ${BASE_URL}/admin"
echo "  Market screen: ${BASE_URL}/market-screen"

if [[ "$LOAD_TEST" == true ]]; then
  echo ""
  echo "==> Load test (50 users)"
  if [[ -f "${ROOT_DIR}/backend/scripts/load_test_50_users.py" ]]; then
    python3 "${ROOT_DIR}/backend/scripts/load_test_50_users.py" \
      --base-url "$BASE_URL" \
      --users 50
  else
    echo "load_test_50_users.py not found" >&2
    exit 1
  fi
fi

echo ""
echo "==> Manual admin steps (before live event)"
echo "  1. Open ${BASE_URL}/admin"
echo "  2. Enter ADMIN_SECRET from .env"
echo "  3. Press RESET (canonical 40-stock universe)"
echo "  4. Do NOT press START until go-live"
echo "  5. Run: ./scripts/oci/backup-db.sh"
