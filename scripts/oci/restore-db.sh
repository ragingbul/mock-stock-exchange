#!/usr/bin/env bash
# Restore PostgreSQL from a pg_dump file.
# Usage: ./scripts/oci/restore-db.sh backups/tradeverse-YYYYMMDD-HHMMSS.sql

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.sql>" >&2
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml"

source .env 2>/dev/null || true
PGUSER="${POSTGRES_USER:-mse}"
PGDB="${POSTGRES_DB:-mock_stock_exchange}"

echo "==> Stopping backend (simulation must not write during restore)"
$COMPOSE stop backend || true

echo "==> Restoring ${PGDB} from ${BACKUP_FILE}"
cat "$BACKUP_FILE" | $COMPOSE exec -T postgres psql -U "$PGUSER" -d "$PGDB"

echo "==> Starting backend"
$COMPOSE start backend

echo "Restore complete."
