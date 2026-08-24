#!/usr/bin/env bash
# Install Docker + Compose on Oracle Linux (opc user). Run once on the VM.
set -euo pipefail

if command -v docker >/dev/null 2>&1 || sudo command -v docker >/dev/null 2>&1; then
  echo "Docker already installed:"
  sudo docker --version 2>/dev/null || docker --version
  exit 0
fi

echo "==> Installing Docker on Oracle Linux"
if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y dnf-plugins-core
  sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true
  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin || \
    sudo dnf install -y docker docker-compose-plugin
elif command -v apt-get >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
else
  curl -fsSL https://get.docker.com | sudo sh
fi

sudo systemctl enable --now docker
sudo usermod -aG docker "$(whoami)"
echo ""
echo "Docker installed. Run: newgrp docker"
echo "Then: docker ps"
echo "Then re-run deploy-quick.sh"
