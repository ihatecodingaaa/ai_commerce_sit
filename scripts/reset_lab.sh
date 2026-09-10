#!/bin/bash
# Reset the entire lab to its known initial state.
#
# Usage:
#   ./scripts/reset_lab.sh                 (native / host install)
#   docker compose exec app scripts/reset_lab.sh              (app data only)
#   docker compose exec --user root app scripts/reset_lab.sh  (also restores
#       the privilege-escalation misconfiguration -- requires root, which is
#       only available for the app CONTAINER, never the real EC2 host)
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== shop-lab reset =="

PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[1/4] recreating database (schema + seed data + fake credentials + KB)"
"$PYTHON_BIN" database/seed.py

echo "[2/5] clearing uploaded files (removes any exploit payloads from prior runs)"
UPLOAD_DIR="${UPLOAD_DIR:-uploads/images}"
rm -rf "${UPLOAD_DIR:?}"/*
mkdir -p "$UPLOAD_DIR"
touch "$UPLOAD_DIR/.gitkeep"

echo "[3/5] clearing admin product photos (products are about to be re-seeded with none)"
PRODUCT_PHOTO_DIR="${PRODUCT_PHOTO_DIR:-media/product_photos}"
rm -rf "${PRODUCT_PHOTO_DIR:?}"/*
mkdir -p "$PRODUCT_PHOTO_DIR"
touch "$PRODUCT_PHOTO_DIR/.gitkeep"

echo "[4/5] clearing logs"
rm -f logs/*.log logs/*.jsonl 2>/dev/null || true

if [ "$(id -u)" = "0" ] && [ -f "vulnerable/privilege_escalation/setup_privesc.sh" ]; then
  echo "[5/5] restoring vulnerable privilege-escalation configuration (running as root)"
  bash vulnerable/privilege_escalation/setup_privesc.sh
else
  echo "[5/5] skipped: not running as root, so the appuser/sudoers/flags"
  echo "      privilege-escalation state was left untouched. This is expected"
  echo "      for a native/non-Docker install (Stages 8-12 only run inside"
  echo "      the app container). To restore it inside Docker, run:"
  echo "        docker compose exec --user root app scripts/reset_lab.sh"
fi

echo "== reset complete =="
