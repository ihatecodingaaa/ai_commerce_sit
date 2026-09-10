#!/bin/bash
# Quick CLI health check against a running instance of the app.
set -euo pipefail

URL="${1:-http://127.0.0.1:5000/health}"

echo "Checking $URL ..."
if command -v curl >/dev/null 2>&1; then
  curl -sS "$URL" | (command -v python3 >/dev/null 2>&1 && python3 -m json.tool || cat)
else
  echo "curl not found" >&2
  exit 1
fi
