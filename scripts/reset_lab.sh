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

echo "[1/7] clearing uploaded files (removes any exploit payloads from prior runs)"
UPLOAD_DIR="${UPLOAD_DIR:-uploads/images}"
rm -rf "${UPLOAD_DIR:?}"/*
mkdir -p "$UPLOAD_DIR"
touch "$UPLOAD_DIR/.gitkeep"

echo "[2/7] clearing admin/catalog-sync product photos (seed.py repopulates the deterministic ones next)"
PRODUCT_PHOTO_DIR="${PRODUCT_PHOTO_DIR:-media/product_photos}"
rm -rf "${PRODUCT_PHOTO_DIR:?}"/*
mkdir -p "$PRODUCT_PHOTO_DIR"
touch "$PRODUCT_PHOTO_DIR/.gitkeep"

echo "[3/7] clearing customer ticket-photo attachments"
TICKET_PHOTO_DIR="${TICKET_PHOTO_DIR:-media/ticket_photos}"
rm -rf "${TICKET_PHOTO_DIR:?}"/*
mkdir -p "$TICKET_PHOTO_DIR"
touch "$TICKET_PHOTO_DIR/.gitkeep"

echo "[4/7] recreating database (schema + seed data + fake credentials + KB + deterministic product photos)"
"$PYTHON_BIN" database/seed.py

echo "[5/7] clearing logs"
rm -f logs/*.log logs/*.jsonl 2>/dev/null || true

echo "[6/7] clearing in-memory chat history (kept in the app process, not on disk -- see app/chatbot/agent.py)"
FLASK_PORT="${FLASK_PORT:-5000}"
if curl -sf -X POST "http://127.0.0.1:${FLASK_PORT}/api/internal/chat/reset-all" -o /dev/null; then
  :
else
  echo "      warning: could not reach the app on 127.0.0.1:${FLASK_PORT} to clear chat memory (is it running?)"
fi

if [ "$(id -u)" = "0" ] && [ -f "vulnerable/privilege_escalation/setup_privesc.sh" ]; then
  echo "[7/7] restoring vulnerable privilege-escalation configuration (running as root)"
  bash vulnerable/privilege_escalation/setup_privesc.sh
else
  echo "[7/7] skipped: not running as root, so the appuser/sudoers/flags"
  echo "      privilege-escalation state was left untouched. This is expected"
  echo "      for a native/non-Docker install (Stages 8-12 only run inside"
  echo "      the app container). To restore it inside Docker, run:"
  echo "        docker compose exec --user root app scripts/reset_lab.sh"
fi

echo "== reset complete =="
