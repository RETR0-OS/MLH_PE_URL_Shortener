#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — add these vars to it:"
  echo "  DROPLET_IP=64.225.10.147"
  echo "  DROPLET_USER=root"
  echo "  DROPLET_PASS=your_password"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${DROPLET_IP:?DROPLET_IP not set in $ENV_FILE}"
: "${DROPLET_USER:?DROPLET_USER not set in $ENV_FILE}"
: "${DROPLET_PASS:?DROPLET_PASS not set in $ENV_FILE}"

BRANCH="${1:-dev}"
REMOTE_DIR="/root/MLH_PE_URL_Shortener"

echo "==> Deploying branch '${BRANCH}' to ${DROPLET_USER}@${DROPLET_IP}"

sshpass -p "$DROPLET_PASS" ssh -o StrictHostKeyChecking=no "${DROPLET_USER}@${DROPLET_IP}" bash -s <<EOF
  set -euo pipefail
  cd ${REMOTE_DIR}

  echo "--- git pull origin ${BRANCH}"
  git stash --quiet 2>/dev/null || true
  git checkout ${BRANCH}
  git pull origin ${BRANCH}
  git stash pop --quiet 2>/dev/null || true

  echo "--- rebuilding containers"
  docker compose up -d --build --remove-orphans

  echo "--- waiting for health check"
  for i in \$(seq 1 30); do
    if curl -sf http://localhost/health > /dev/null 2>&1; then
      echo "--- healthy after \${i}s"
      break
    fi
    sleep 1
  done

  if ! curl -sf http://localhost/health > /dev/null 2>&1; then
    echo "!!! health check failed after 30s"
    docker compose logs --tail=20 app
    exit 1
  fi

  echo "--- deploy complete"
  docker compose ps --format "table {{.Name}}\t{{.Status}}"
EOF
