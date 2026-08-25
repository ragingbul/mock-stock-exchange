#!/usr/bin/env bash
# Start TRADEVERSE local LAN stack (HTTP port 80 via nginx).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.local.yml"

if [[ ! -f .env ]]; then
  echo "Missing .env — run ./scripts/local/setup-env.sh (or copy .env.local.example to .env)." >&2
  exit 1
fi

echo "==> Build images"
$COMPOSE build

echo "==> Start postgres"
$COMPOSE up -d postgres

echo "==> Wait for postgres"
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-mse}" -d "${POSTGRES_DB:-mock_stock_exchange}" >/dev/null 2>&1; do
  sleep 2
done

echo "==> Run migrations"
$COMPOSE run --rm backend alembic upgrade head

echo "==> Start all services"
$COMPOSE up -d

FRONTEND_URL=""
if [[ -f .env ]]; then
  FRONTEND_URL="$(grep -E '^FRONTEND_URL=' .env | head -1 | cut -d= -f2- | tr -d '\r' || true)"
fi

echo ""
echo "TRADEVERSE is running."
echo "  Localhost:  http://localhost/terminal"
echo "  LAN:        http://<YOUR_LAN_IP>/terminal  (find IP: ipconfig on Windows)"
if [[ -n "${FRONTEND_URL:-}" && "${FRONTEND_URL}" == https://* ]]; then
  echo "  Public:     ${FRONTEND_URL}/terminal"
fi
echo "  Admin:      http://localhost/admin"
echo "  Health:     http://localhost/api/v1/health"
echo ""
echo "Share over the internet: ./scripts/local/share.sh   (starts ngrok + updates CORS)"
echo "Verify:                  ./scripts/local/health-check.sh"
