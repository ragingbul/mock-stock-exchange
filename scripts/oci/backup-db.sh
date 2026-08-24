#!/usr/bin/env bash
# PostgreSQL backup to ./backups/tradeverse-YYYYMMDD-HHMMSS.sql

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR="${ROOT_DIR}/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/tradeverse-${STAMP}.sql"

mkdir -p "$BACKUP_DIR"

source .env 2>/dev/null || true
PGUSER="${POSTGRES_USER:-mse}"
PGDB="${POSTGRES_DB:-mock_stock_exchange}"

echo "==> Backing up ${PGDB} to ${OUT}"
$COMPOSE exec -T postgres pg_dump -U "$PGUSER" -d "$PGDB" --no-owner --no-acl > "$OUT"
echo "Backup complete: $OUT"
