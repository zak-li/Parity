#!/usr/bin/env bash
# Deploy the Parity backend stack (API + Redis + MLflow + Spark) to a remote
# host over SSH. Databases stay in the cloud (configured in .env).
#
#   ./scripts/ops/deploy_vm.sh <ssh-user> [host]
#   e.g.  ./scripts/ops/deploy_vm.sh ubuntu 10.10.10.150
#
# Requires: ssh access to the VM, and sudo on the VM (to install Docker if it
# is not already present). Reads secrets from .env (must exist).
set -euo pipefail

VM_USER="${1:?usage: deploy_vm.sh <ssh-user> [host]}"
VM_HOST="${2:-10.10.10.150}"
TARGET="parity"
REMOTE="${VM_USER}@${VM_HOST}"

cd "$(dirname "$0")/../.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found (API config/secrets). Aborting." >&2
  exit 1
fi

echo "==> [1/4] Copying project to ${REMOTE}:~/${TARGET} ..."
tar czf - \
  --exclude='node_modules' \
  --exclude='.angular' \
  --exclude='dist' \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./.mypy_cache' \
  --exclude='./.pytest_cache' \
  --exclude='./.ruff_cache' \
  --exclude='./tmp' \
  . | ssh "${REMOTE}" "rm -rf ~/${TARGET} && mkdir -p ~/${TARGET} && tar xzf - -C ~/${TARGET}"

echo "==> [2/4] Ensuring Docker + compose plugin are installed ..."
ssh "${REMOTE}" 'bash -s' <<'EOSSH'
set -e
if ! command -v docker >/dev/null 2>&1; then
  echo "  installing Docker ..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
if ! docker compose version >/dev/null 2>&1; then
  sudo apt-get update -y && sudo apt-get install -y docker-compose-plugin || true
fi
docker --version
docker compose version
EOSSH

echo "==> [3/4] Building and starting the stack (this can take a few minutes) ..."
ssh "${REMOTE}" "cd ~/${TARGET} && sudo docker compose up -d --build"

echo "==> [4/4] Status:"
ssh "${REMOTE}" "cd ~/${TARGET} && sudo docker compose ps"

echo ""
echo "Done. Frontend: http://${VM_HOST}    API: http://${VM_HOST}:8000/health"
echo "Remember to add http://${VM_HOST} to Auth0 Allowed Callback/Logout URLs & Web Origins."
