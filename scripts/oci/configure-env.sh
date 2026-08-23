#!/usr/bin/env bash
# Generate production .env for Oracle deployment.
#
# Usage:
#   ./scripts/oci/configure-env.sh 203-0-113-10.sslip.io
#   ./scripts/oci/configure-env.sh 203.0.113.10          # auto-converts to sslip.io
#   ./scripts/oci/configure-env.sh --self-signed 203.0.113.10

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

SELF_SIGNED=false
HOST_OR_IP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --self-signed) SELF_SIGNED=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--self-signed] <hostname-or-ip>"
      exit 0
      ;;
    *)
      HOST_OR_IP="$1"
      shift
      ;;
  esac
done

if [[ -z "$HOST_OR_IP" ]]; then
  echo "Usage: $0 [--self-signed] <hostname-or-ip>" >&2
  exit 1
fi

if [[ "$HOST_OR_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  if [[ "$SELF_SIGNED" == true ]]; then
    BASE_URL="https://${HOST_OR_IP}"
  else
    HOSTNAME="$("${ROOT_DIR}/scripts/oci/sslip-hostname.sh" "$HOST_OR_IP")"
    BASE_URL="https://${HOSTNAME}"
  fi
else
  BASE_URL="https://${HOST_OR_IP}"
fi

JWT_SECRET="$(openssl rand -hex 32)"
ADMIN_SECRET="$(openssl rand -hex 16)"
POSTGRES_PASSWORD="$(openssl rand -hex 16)"

cat > .env <<EOF
# TRADEVERSE — Oracle Cloud production (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))
ENVIRONMENT=production
DEBUG=false
AUTO_INIT_DB=false
SIMULATION_SPEED=1

POSTGRES_USER=mse
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=mock_stock_exchange

JWT_SECRET=${JWT_SECRET}
ADMIN_SECRET=${ADMIN_SECRET}

FRONTEND_URL=${BASE_URL}
BACKEND_URL=${BASE_URL}
CORS_ORIGINS=${BASE_URL}

NEXT_PUBLIC_API_URL=${BASE_URL}
NEXT_PUBLIC_WS_URL=${BASE_URL/https:/wss:}
NEXT_PUBLIC_API_PREFIX=/api/v1
EOF

chmod 600 .env

echo "==> Wrote ${ROOT_DIR}/.env"
echo "    Public URL: ${BASE_URL}"
echo "    ADMIN_SECRET: ${ADMIN_SECRET}"
echo ""
echo "Save ADMIN_SECRET — you need it for /admin"
echo "Next: TLS setup then ./scripts/oci/deploy.sh"
