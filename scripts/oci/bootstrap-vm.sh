#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu 22.04 Oracle VM for TRADEVERSE.
# Run once after SSH login (as ubuntu user with sudo).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ragingbul/mock-stock-exchange/main/scripts/oci/bootstrap-vm.sh | bash
#   # or from a cloned repo:
#   ./scripts/oci/bootstrap-vm.sh

set -euo pipefail

REPO_URL="${TRADEVERSE_REPO_URL:-https://github.com/ragingbul/mock-stock-exchange.git}"
INSTALL_DIR="${TRADEVERSE_DIR:-$HOME/tradeverse}"
BRANCH="${TRADEVERSE_BRANCH:-main}"

echo "==> TRADEVERSE Oracle VM bootstrap"
echo "    Repo: ${REPO_URL}"
echo "    Dir:  ${INSTALL_DIR}"

echo "==> System packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
sudo apt-get install -y -qq ca-certificates curl git openssl ufw python3

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. You may need to run: newgrp docker"
fi

echo "==> Host firewall (ufw)"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
echo "y" | sudo ufw enable || true
sudo ufw status

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "==> Cloning repository"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
else
  echo "==> Repository exists at ${INSTALL_DIR}"
fi

cd "$INSTALL_DIR"
chmod +x scripts/oci/*.sh

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example — edit secrets before deploy"
fi

PUBLIC_IP="$(curl -fsSL -4 ifconfig.me 2>/dev/null || curl -fsSL -4 icanhazip.com 2>/dev/null || true)"
if [[ -n "$PUBLIC_IP" ]]; then
  HOSTNAME="$("${INSTALL_DIR}/scripts/oci/sslip-hostname.sh" "$PUBLIC_IP")"
  echo ""
  echo "==> Detected public IP: ${PUBLIC_IP}"
  echo "==> Suggested sslip.io hostname: ${HOSTNAME}"
  echo ""
  echo "Next steps:"
  echo "  cd ${INSTALL_DIR}"
  echo "  ./scripts/oci/configure-env.sh ${HOSTNAME}"
  echo "  ./scripts/oci/setup-letsencrypt.sh ${PUBLIC_IP}"
  echo "  ./scripts/oci/deploy.sh"
  echo "  ./scripts/oci/verify-deployment.sh"
else
  echo "Could not detect public IP — set hostname manually in configure-env.sh"
fi
