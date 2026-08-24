#!/usr/bin/env bash
# Install Docker + Compose on Oracle Linux (OL8/OL9). Run on the VM as opc.
set -euo pipefail

if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
  echo "Docker already works: $(docker --version)"
  docker compose version 2>/dev/null || docker-compose version 2>/dev/null || true
  exit 0
fi

if sudo command -v docker >/dev/null 2>&1 && sudo docker ps >/dev/null 2>&1; then
  echo "Docker works via sudo: $(sudo docker --version)"
  exit 0
fi

echo "==> Installing Docker on Oracle Linux"

if ! command -v dnf >/dev/null 2>&1; then
  echo "ERROR: dnf not found — this script is for Oracle Linux / RHEL" >&2
  exit 1
fi

# Remove conflicting podman-docker if broken, then install Docker CE from Docker repo (CentOS-compatible)
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true

if ! sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
  echo "==> Docker CE failed — trying distribution docker package"
  sudo dnf install -y docker docker-compose-plugin || sudo dnf install -y docker
fi

sudo systemctl enable --now docker
sudo usermod -aG docker "$(whoami)"

echo ""
echo "==> Installed:"
sudo docker --version
sudo docker compose version 2>/dev/null || true

echo ""
echo "Run: newgrp docker"
echo "Then: docker ps"
echo "Then re-run deploy-quick.sh"
