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

# Scatter ordinary-looking transient files in /tmp so a foothold account can't
# trivially tell the one path that matters from normal host cruft. All
# synthetic, no sensitive data; regenerated each start.
seed_tmp_decoys() {
  local rid
  rid="$(tr -dc 'a-f0-9' </dev/urandom 2>/dev/null | head -c8 || echo deadbeef)"
  {
    mkdir -p "/tmp/pip-build-${rid}" "/tmp/.cache/fontconfig" "/tmp/magick-${rid}" 2>/dev/null
    printf '%s GET /health 200\n%s GET /products 200\n%s POST /api/chat 200\n' \
      "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
      > "/tmp/gunicorn-access-${rid}.log" 2>/dev/null
    printf 'worker booting\nlistening at http://0.0.0.0:80\n' > "/tmp/app-boot-${rid}.log" 2>/dev/null
    : > "/tmp/.s.PGSQL.5432.lock" 2>/dev/null
    printf 'cache_version=3\nlast_sweep=%s\n' "$(date -u '+%s')" > "/tmp/.cache/sweep.state" 2>/dev/null
  } || true
}
seed_tmp_decoys || true

exec "$@"
