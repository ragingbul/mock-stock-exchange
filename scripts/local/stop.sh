#!/usr/bin/env bash
# Stop TRADEVERSE local LAN stack (preserves database volume).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

docker compose -f docker-compose.local.yml down
echo "Stopped. Database volume postgres_data_local preserved."
