#!/usr/bin/env bash
# Deploy or update TRADEVERSE on Oracle Always Free VM.
# Does NOT remove database volumes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example and configure for OCI production." >&2
  exit 1
fi

if [[ ! -f nginx/certs/fullchain.pem || ! -f nginx/certs/privkey.pem ]]; then
  echo "Missing TLS certs in nginx/certs/ — run scripts/oci/generate-self-signed-cert.sh first." >&2
  exit 1
fi

echo "==> Pull latest code (if git repo)"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git pull --ff-only || echo "Warning: git pull failed; continuing with current tree"
fi

echo "==> Build images"
$COMPOSE build

echo "==> Start postgres (if not running)"
$COMPOSE up -d postgres

echo "==> Wait for postgres"
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-mse}" -d "${POSTGRES_DB:-mock_stock_exchange}" >/dev/null 2>&1; do
  sleep 2
done

echo "==> Run migrations (once per deploy)"
$COMPOSE run --rm backend alembic upgrade head

echo "==> Start all services"
$COMPOSE up -d

echo "==> Done. Run scripts/oci/health-check.sh to verify."
