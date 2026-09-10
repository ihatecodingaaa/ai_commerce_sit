#!/bin/bash
# Native (non-Docker) setup for the application + database portion of the
# lab (Stages 1-7: browsing, chatbot, RAG-based indirect prompt injection,
# credential disclosure, internal image API). This script deliberately does
# NOT provision the privilege-escalation misconfiguration (appuser/shopops/
# sudoers/root flag) -- that only happens inside the Docker app container
# (see Dockerfile.app and vulnerable/privilege_escalation/), so a compromise
# of Stages 8-12 never touches your real EC2 host. Use Docker (README.md
# "Docker setup") to run the full attack chain end to end.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== shop-lab native setup =="

echo "[1/5] checking for python3"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"
"$PYTHON_BIN" --version

echo "[2/5] creating virtualenv (.venv)"
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/5] installing Python dependencies"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "[4/5] preparing .env"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  created .env from .env.example (edit it if needed)"
fi

mkdir -p logs uploads/images database

echo "[5/5] seeding database"
"$PYTHON_BIN" database/seed.py

cat <<'EOF'

Setup complete.

Next steps:
  1. Make sure Ollama is installed and running:  scripts/install_ollama.sh
  2. Start the app:                              python run.py
  3. Visit:                                       http://127.0.0.1:5000

For the full attack chain including code execution / privilege escalation
(Stages 8-12), use the Docker setup instead -- see README.md.
EOF
