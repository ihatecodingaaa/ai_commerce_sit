#!/bin/bash
# Container entrypoint: seed the database on first start (if it doesn't
# already exist), then run the app. Keeps `docker compose up -d` alone
# sufficient for a clean checkout -- no manual seed step required.
set -euo pipefail

cd /opt/shop

DB_PATH="${DATABASE_URL:-database/shop_lab.db}"
if [ ! -f "$DB_PATH" ]; then
  echo "[entrypoint] no database found at $DB_PATH -- seeding"
  python database/seed.py
else
  echo "[entrypoint] database already present at $DB_PATH -- leaving as is"
  echo "[entrypoint] (run scripts/reset_lab.sh to force a clean reset)"
fi

exec "$@"
