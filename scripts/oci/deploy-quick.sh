#!/usr/bin/env bash
# Quick deploy when Docker is already installed (Oracle Linux / Ubuntu).
# Run as opc or ubuntu on the VM after SSH login.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ragingbul/mock-stock-exchange/cursor/oracle-cloud-deploy-e37a/scripts/oci/deploy-quick.sh | bash
#   # or from cloned repo:
#   ./scripts/oci/deploy-quick.sh

set -euo pipefail

REPO_URL="${TRADEVERSE_REPO_URL:-https://github.com/ragingbul/mock-stock-exchange.git}"
BRANCH="${TRADEVERSE_BRANCH:-cursor/oracle-cloud-deploy-e37a}"
INSTALL_DIR="${TRADEVERSE_DIR:-$HOME/tradeverse}"
PUBLIC_IP="${PUBLIC_IP:-$(curl -fsSL -4 --max-time 10 ifconfig.me 2>/dev/null || curl -fsSL -4 --max-time 10 icanhazip.com 2>/dev/null || true)}"

if [[ -z "$PUBLIC_IP" ]]; then
  echo "Could not detect public IP. Set it manually:" >&2
  echo "  PUBLIC_IP=152.67.10.105 ./scripts/oci/deploy-quick.sh" >&2
  exit 1
fi

echo "==> TRADEVERSE quick deploy (Docker pre-installed)"
echo "    IP: ${PUBLIC_IP}"
echo "    Dir: ${INSTALL_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker first." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1 && ! docker-compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose not found." >&2
  exit 1
fi

# Ensure user can run docker (opc often needs group or newgrp)
if ! docker ps >/dev/null 2>&1; then
  echo "==> Adding $(whoami) to docker group (may need re-login)"
  sudo usermod -aG docker "$(whoami)" || true
  if ! sg docker -c "docker ps" >/dev/null 2>&1; then
    echo "WARN: run 'newgrp docker' or re-SSH, then re-run this script" >&2
    DOCKER="sudo docker"
  else
    DOCKER="sg docker -c"
  fi
else
  DOCKER=""
fi

run_docker() {
  if [[ -n "$DOCKER" ]]; then
    sg docker -c "$*"
  else
    eval "$@"
  fi
}

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "==> Cloning repository"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
else
  echo "==> Updating repository"
  git -C "$INSTALL_DIR" fetch origin "$BRANCH" || true
  git -C "$INSTALL_DIR" checkout "$BRANCH" 2>/dev/null || git -C "$INSTALL_DIR" checkout main
  git -C "$INSTALL_DIR" pull --ff-only || true
fi

cd "$INSTALL_DIR"
chmod +x scripts/oci/*.sh

echo "==> Configure .env"
./scripts/oci/configure-env.sh "$PUBLIC_IP"

echo "==> TLS certificate"
if command -v certbot >/dev/null 2>&1 || sudo dnf install -y certbot 2>/dev/null || sudo apt-get install -y certbot 2>/dev/null; then
  if ./scripts/oci/setup-letsencrypt.sh "$PUBLIC_IP"; then
    echo "Let's Encrypt certificate installed"
  else
    echo "Certbot failed — using self-signed certificate"
    ./scripts/oci/generate-self-signed-cert.sh "$PUBLIC_IP"
  fi
else
  echo "Certbot not available — using self-signed certificate"
  ./scripts/oci/generate-self-signed-cert.sh "$PUBLIC_IP"
fi

echo "==> Deploy stack"
./scripts/oci/deploy.sh

echo "==> Verify"
./scripts/oci/verify-deployment.sh || true

HOSTNAME="$("./scripts/oci/sslip-hostname.sh" "$PUBLIC_IP")"
echo ""
echo "==> DONE"
echo "  Terminal:      https://${HOSTNAME}/terminal"
echo "  Admin:         https://${HOSTNAME}/admin"
echo "  Market screen: https://${HOSTNAME}/market-screen"
echo ""
echo "  ADMIN_SECRET is in ${INSTALL_DIR}/.env"
echo "  Admin: RESET before event, do NOT START until go-live"
