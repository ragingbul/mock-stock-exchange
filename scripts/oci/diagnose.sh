#!/usr/bin/env bash
# Quick pipeline diagnostics for TradeVerse on Oracle VM.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "=== TradeVerse diagnose ==="
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

echo "==> Container status"
$COMPOSE ps
echo

echo "==> Resource usage (snapshot)"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
echo

echo "==> Backend health (10s timeout)"
if curl -skf --max-time 10 https://127.0.0.1/api/v1/health | python3 -m json.tool; then
  echo "Health: OK"
else
  echo "Health: FAILED"
fi
echo

echo "==> Recent backend logs (last 30 lines)"
$COMPOSE logs --tail=30 backend 2>/dev/null || true
echo

echo "==> Recent nginx errors (last 15 lines)"
$COMPOSE logs --tail=15 nginx 2>/dev/null | grep -i error || echo "(no recent nginx errors)"
echo

echo "==> Postgres ready"
$COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-mse}" -d "${POSTGRES_DB:-mock_stock_exchange}" 2>/dev/null || echo "postgres check failed"
echo

echo "=== Done ==="
echo "If health failed: docker compose -f docker-compose.prod.yml restart backend nginx"
echo "If logs show QueuePool limit: deploy latest (pool fix) then restart backend"
echo "If sim frozen: admin STOP then START, or RESET before go-live"
