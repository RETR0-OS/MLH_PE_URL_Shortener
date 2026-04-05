#!/bin/bash
# =============================================================================
# DigitalOcean User Data Script — MLH PE URL Shortener
# =============================================================================
# Paste this into the "User Data" field when creating a new Droplet.
# On first boot it will:
#   1. Install Docker
#   2. Configure UFW firewall
#   3. Clone the repo (dev branch)
#   4. Build and start all 14 services with Docker Compose
#
# Requirements: Ubuntu 24.04 LTS, 4 vCPU / 8 GB RAM (or larger)
# Logs: /var/log/mlh-startup.log
# =============================================================================

set -euo pipefail
exec > >(tee /var/log/mlh-startup.log) 2>&1

echo "=========================================="
echo " MLH URL Shortener — startup $(date)"
echo "=========================================="

# --- System update ---------------------------------------------------------
echo "[1/5] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl git ufw

# --- Docker ----------------------------------------------------------------
echo "[2/5] Installing Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

echo "Docker version: $(docker --version)"
echo "Compose version: $(docker compose version)"

# --- Firewall --------------------------------------------------------------
echo "[3/5] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP  (Nginx)
ufw allow 443/tcp   # HTTPS (Nginx)
ufw allow 3000/tcp  # Grafana
ufw allow 9090/tcp  # Prometheus
ufw allow 9093/tcp  # Alertmanager
ufw allow 16686/tcp # Jaeger UI
# Internal services (Postgres 5432, Redis 6379) are intentionally NOT opened
ufw --force enable
echo "UFW status:"
ufw status

# --- Clone repo ------------------------------------------------------------
echo "[4/5] Cloning repository (dev branch)..."
REPO_URL="https://github.com/RETR0-OS/MLH_PE_URL_Shortener.git"
REPO_DIR="/root/MLH_PE_URL_Shortener"

if [ -d "$REPO_DIR" ]; then
  echo "Repo already exists, pulling latest..."
  git -C "$REPO_DIR" fetch origin dev
  git -C "$REPO_DIR" reset --hard origin/dev
else
  git clone -b dev "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
echo "Latest commit: $(git log --oneline -1)"

# --- Docker Compose --------------------------------------------------------
echo "[5/5] Building and starting all services..."
docker compose up -d --build

# --- Health check ----------------------------------------------------------
echo ""
echo "Waiting for app to become healthy..."
for i in $(seq 1 30); do
  if curl -sf http://localhost/health > /dev/null 2>&1; then
    echo "✓ App is healthy!"
    break
  fi
  echo "  attempt $i/30 — waiting 5s..."
  sleep 5
done

# --- Final status ----------------------------------------------------------
echo ""
echo "=========================================="
echo " Service status"
echo "=========================================="
docker compose ps

DROPLET_IP=$(curl -sf http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo " Deployment complete! $(date)"
echo "=========================================="
echo ""
echo " App (HTTP)   : http://${DROPLET_IP}"
echo " App (HTTPS)  : https://${DROPLET_IP}"
echo " Swagger docs : http://${DROPLET_IP}/docs"
echo " Grafana      : http://${DROPLET_IP}:3000  (admin / admin)"
echo " Prometheus   : http://${DROPLET_IP}:9090"
echo " Jaeger       : http://${DROPLET_IP}:16686"
echo " Alertmanager : http://${DROPLET_IP}:9093"
echo ""
echo " Full log: /var/log/mlh-startup.log"
echo "=========================================="
