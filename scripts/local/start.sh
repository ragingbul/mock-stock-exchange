#!/usr/bin/env bash
# Start TRADEVERSE local LAN stack (HTTP port 80 via nginx).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.local.yml"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.local.example to .env and configure." >&2
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

echo ""
echo "TRADEVERSE is running."
echo "  Localhost:  http://localhost/terminal"
echo "  LAN:        http://<YOUR_LAN_IP>/terminal  (find IP: ipconfig on Windows)"
echo "  Admin:      http://localhost/admin"
echo "  Health:     http://localhost/api/v1/health"
echo ""
echo "Run scripts/local/health-check.sh to verify."
