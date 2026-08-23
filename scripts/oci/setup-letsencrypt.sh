#!/usr/bin/env bash
# Obtain Let's Encrypt certificate for sslip.io hostname (free HTTPS, no browser warnings).
#
# Prerequisites:
#   - VM public IP assigned; ports 80 and 443 open in OCI security list + ufw
#   - DNS not required — sslip.io resolves automatically from the hostname
#   - Run from repo root on the Oracle VM (stop nginx if already running on :80)
#
# Usage:
#   ./scripts/oci/setup-letsencrypt.sh 203.0.113.10
#   ./scripts/oci/setup-letsencrypt.sh 203-0-113-10.sslip.io

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
CERT_DIR="${ROOT_DIR}/nginx/certs"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <PUBLIC_IP_or_sslip_hostname>" >&2
  exit 1
fi

INPUT="$1"
if [[ "$INPUT" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  HOSTNAME="$("${ROOT_DIR}/scripts/oci/sslip-hostname.sh" "$INPUT")"
else
  HOSTNAME="${INPUT%.}"
fi

EMAIL="${CERTBOT_EMAIL:-admin@${HOSTNAME}}"

echo "==> Hostname: ${HOSTNAME}"
echo "==> Email: ${EMAIL}"

if ! command -v certbot >/dev/null 2>&1; then
  echo "==> Installing certbot"
  sudo apt-get update -qq
  sudo apt-get install -y -qq certbot
fi

mkdir -p "$CERT_DIR"

# Stop nginx container if running so certbot can bind :80
if docker compose -f docker-compose.prod.yml ps nginx 2>/dev/null | grep -q Up; then
  echo "==> Stopping nginx container for standalone certbot"
  docker compose -f docker-compose.prod.yml stop nginx || true
fi

echo "==> Requesting certificate (standalone mode on port 80)"
sudo certbot certonly --standalone \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  -d "$HOSTNAME"

LE_LIVE="/etc/letsencrypt/live/${HOSTNAME}"
if [[ ! -f "${LE_LIVE}/fullchain.pem" ]]; then
  echo "Certbot failed — expected ${LE_LIVE}/fullchain.pem" >&2
  exit 1
fi

echo "==> Copying certs to nginx/certs/"
sudo cp "${LE_LIVE}/fullchain.pem" "${CERT_DIR}/fullchain.pem"
sudo cp "${LE_LIVE}/privkey.pem" "${CERT_DIR}/privkey.pem"
sudo chown "$(whoami):$(whoami)" "${CERT_DIR}/fullchain.pem" "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"
chmod 600 "${CERT_DIR}/privkey.pem"

echo ""
echo "Certificate installed for https://${HOSTNAME}"
echo "Update .env URLs to https://${HOSTNAME} then run: ./scripts/oci/deploy.sh"
echo ""
echo "Renewal (add to crontab):"
echo "  0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/${HOSTNAME}/fullchain.pem ${CERT_DIR}/ && cp /etc/letsencrypt/live/${HOSTNAME}/privkey.pem ${CERT_DIR}/ && docker compose -f ${ROOT_DIR}/docker-compose.prod.yml restart nginx"
