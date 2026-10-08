#!/bin/bash
# Provisions the deterministic local privilege-escalation misconfiguration
# inside the app container. Run as root, once at image build time and again
# by scripts/reset_lab.sh to restore the vulnerable state after a student
# (deliberately or accidentally) breaks it.
#
# A single, strict, three-tier chain -- low (appuser) -> mid (opsuser) ->
# high (root) -- with exactly one viable technique at each hop, no group
# membership anywhere, and no alternate/shortcut route to either hop:
#
#   Hop 1 (appuser -> opsuser): appuser has exactly one sudo grant --
#   NOPASSWD to run archive_worker.py *as opsuser*, nothing else, and
#   cannot edit that script. The script imports an "archive format
#   handler" module by name from a shared outbox directory that IS
#   writable by appuser (CWE-427, uncontrolled search path element), and
#   its only defense -- a checksum manifest -- is itself stored in that
#   same appuser-writable directory (CWE-354, improper validation of an
#   integrity check value an attacker can also regenerate). opsuser has
#   no password at all (the account is locked), so this exploit is the
#   *only* way to become opsuser.
#
#   Hop 2 (opsuser -> root): opsuser has NO sudo grant at all -- `sudo -l`
#   shows nothing. Instead, opsuser can read a core dump
#   (backups/diagnostics/rootwatch.core) left behind by `rootwatch`, a
#   health-check tool that decrypts root's real account password from an
#   AES-256-GCM-"protected" blob using a key stored right next to it. It
#   scrubs the decrypted password after use (so `strings` on the dump finds
#   nothing) but never scrubs the key or ciphertext, then crashes. With no
#   real key custody, the key+blob left live in memory hand opsuser root's
#   actual password via `gdb` forensics on the core dump and one real
#   AES-256-GCM decrypt -- then `su -`.
#
# See archive_worker.py, rootwatch.c, gen_root_secret.py, and README.md
# for the full writeup.
set -euo pipefail

SHOP_ROOT="/opt/shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[privesc-setup] provisioning appuser (low) and opsuser (mid) accounts"
id -u appuser >/dev/null 2>&1 || useradd -m -s /bin/bash appuser
id -u opsuser >/dev/null 2>&1 || useradd -m -s /bin/bash opsuser
# opsuser has no valid password at all: useradd with no -p leaves the
# shadow password field locked ("!", not empty -- an empty field would
# mean "no password required", the opposite of what's wanted here).
# usermod -L is belt-and-suspenders in case opsuser already existed from
# a prior provision with some other state.
usermod -L opsuser

echo "[privesc-setup] laying out $SHOP_ROOT"
mkdir -p "$SHOP_ROOT/scripts" "$SHOP_ROOT/scripts/rootwatch" \
         "$SHOP_ROOT/backups" "$SHOP_ROOT/backups/outbox" "$SHOP_ROOT/backups/diagnostics" \
         "$SHOP_ROOT/flags" "$SHOP_ROOT/uploads/images" "$SHOP_ROOT/media/product_photos" \
         "$SHOP_ROOT/database" "$SHOP_ROOT/logs"
# root-owned, not writable by appuser or opsuser -- neither hop's target
# can be tampered with directly; the exploits below are the only route in.
chown root:root "$SHOP_ROOT/scripts"
chmod 755 "$SHOP_ROOT/scripts"

echo "[privesc-setup] preparing appuser-writable outbox dir (Hop 1's search-path bug)"
touch "$SHOP_ROOT/backups/outbox/.placeholder"
chown -R appuser:appuser "$SHOP_ROOT/backups/outbox"
chmod 755 "$SHOP_ROOT/backups/outbox"  # world-readable/executable so opsuser's
                                        # import can read it -- only appuser can write

echo "[privesc-setup] seeding archive-format handlers + manifest in the outbox"
OUTBOX="$SHOP_ROOT/backups/outbox"

cat > "$OUTBOX/noop.py" <<'EOF'
"""No-op archive handler: used for dry runs and smoke tests."""
def archive():
    pass
EOF

cat > "$OUTBOX/tar_gzip.py" <<'EOF'
"""tar.gz archive handler: bundle processed images into a dated tarball."""
import os, tarfile, time

ARCHIVE_ROOT = "/opt/shop/backups/cold"

def archive():
    os.makedirs(ARCHIVE_ROOT, exist_ok=True)
    dest = os.path.join(ARCHIVE_ROOT, "images-%s.tar.gz" % time.strftime("%Y%m%d"))
    src = "/opt/shop/uploads/images"
    if os.path.isdir(src):
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(src, arcname="images")
EOF

cat > "$OUTBOX/s3_offload.py" <<'EOF'
"""Cold object-storage handler: offload archived images to the backup bucket.

Credentials come from the environment (S3_BUCKET / AWS_*). If unset this
handler no-ops so a misconfigured host doesn't fail the nightly archive run.
"""
import os

def archive():
    if not os.environ.get("S3_BUCKET"):
        return
    # Upload handled by the nightly maintenance job; omitted in this build.
EOF

cat > "$OUTBOX/local_cold.py" <<'EOF'
"""Local cold-storage handler: copy processed images to the cold tier."""
import os, shutil

COLD = "/opt/shop/backups/cold/images"

def archive():
    os.makedirs(COLD, exist_ok=True)
    src = "/opt/shop/uploads/images"
    if os.path.isdir(src):
        for name in os.listdir(src):
            try:
                shutil.copy2(os.path.join(src, name), os.path.join(COLD, name))
            except OSError:
                pass
EOF

cat > "$OUTBOX/README" <<'EOF'
Archive-format handlers
=======================

Pluggable handlers for the nightly cold-storage archive job. Each handler
implements a single archive() entry point and is selected by name from the
maintenance tooling. Managed by Infrastructure (owner: Priya Nair) -- see the
internal runbook before adding or changing a format.
EOF

# Build the manifest from every handler present (name -> sha256 of its module).
python3 - "$OUTBOX" <<'PY'
import hashlib, json, os, sys
outbox = sys.argv[1]
manifest = {}
for fn in sorted(os.listdir(outbox)):
    if fn.endswith(".py"):
        with open(os.path.join(outbox, fn), "rb") as f:
            manifest[fn[:-3]] = hashlib.sha256(f.read()).hexdigest()
with open(os.path.join(outbox, "handlers.manifest"), "w") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
PY

chown -R appuser:appuser "$OUTBOX"

echo "[privesc-setup] installing archive_worker.py, root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/archive_worker.py" "$SHOP_ROOT/scripts/archive_worker.py"

echo "[privesc-setup] installing benign maintenance scripts (recon noise alongside the real target)"
cat > "$SHOP_ROOT/scripts/healthcheck.sh" <<'EOF'
#!/bin/bash
# Periodic health probe used by the platform monitor.
curl -fsS "http://127.0.0.1:${FLASK_PORT:-80}/health" || exit 1
EOF
cat > "$SHOP_ROOT/scripts/db_backup.py" <<'EOF'
#!/usr/bin/env python3
"""Nightly SQLite snapshot into the backups tree."""
import datetime, pathlib, shutil

DB = pathlib.Path("/opt/shop/database/shop_lab.db")
DEST = pathlib.Path("/opt/shop/backups/db")

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        shutil.copy2(DB, DEST / ("shop_lab-%s.db" % datetime.date.today().isoformat()))

if __name__ == "__main__":
    main()
EOF
chmod 755 "$SHOP_ROOT/scripts/healthcheck.sh" "$SHOP_ROOT/scripts/db_backup.py"
chown root:root "$SHOP_ROOT/scripts/healthcheck.sh" "$SHOP_ROOT/scripts/db_backup.py"

echo "[privesc-setup] installing sudo rule -- Hop 1 only, opsuser gets NONE"
cat > /etc/sudoers.d/shop-archive <<'EOF'
appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *
EOF
chmod 440 /etc/sudoers.d/shop-archive
visudo -cf /etc/sudoers.d/shop-archive
# Deliberately no /etc/sudoers.d/shop-ops this time -- `sudo -l` as opsuser
# shows nothing. Hop 2 is not a sudo-trust-boundary bug at all.
rm -f /etc/sudoers.d/shop-ops

echo "[privesc-setup] generating Hop 2 root credential + AES-256-GCM blob"
ROOTWATCH_DIR="$SHOP_ROOT/scripts/rootwatch"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"
ROOT_PASSWORD="$("$PYTHON_BIN" "$SCRIPT_DIR/gen_root_secret.py" \
    "$ROOTWATCH_DIR/root_secret.key" "$ROOTWATCH_DIR/root_secret.enc")"
chown root:root "$ROOTWATCH_DIR/root_secret.key" "$ROOTWATCH_DIR/root_secret.enc"
chmod 600 "$ROOTWATCH_DIR/root_secret.key" "$ROOTWATCH_DIR/root_secret.enc"
echo "root:${ROOT_PASSWORD}" | chpasswd

echo "[privesc-setup] compiling rootwatch (Hop 2 target), root-owned"
gcc -O0 -g -o "$ROOTWATCH_DIR/rootwatch" "$SCRIPT_DIR/rootwatch.c" -lcrypto
chown root:root "$ROOTWATCH_DIR/rootwatch"
chmod 755 "$ROOTWATCH_DIR/rootwatch"

echo "[privesc-setup] running rootwatch once under gdb to capture its deterministic crash dump"
# generate-core-file writes a real ELF core file directly, independent of
# the host's own /proc/sys/kernel/core_pattern (which this lab must not
# touch -- it's a host-wide kernel setting, out of scope for a container).
# This keeps the dump 100% reproducible across any host/CI configuration.
GDB_LOG="$(mktemp)"
gdb -q -batch \
    -ex "set pagination off" \
    -ex "run \"$ROOTWATCH_DIR/root_secret.key\" \"$ROOTWATCH_DIR/root_secret.enc\"" \
    -ex "generate-core-file $SHOP_ROOT/backups/diagnostics/rootwatch.core" \
    -ex "quit" \
    "$ROOTWATCH_DIR/rootwatch" > "$GDB_LOG" 2>&1 || true
if [ ! -f "$SHOP_ROOT/backups/diagnostics/rootwatch.core" ]; then
    echo "[privesc-setup] ERROR: rootwatch.core was not produced -- gdb output:" >&2
    cat "$GDB_LOG" >&2
    exit 1
fi
rm -f "$GDB_LOG"
# opsuser-owned, readable only by its owner -- appuser (a different
# account entirely) cannot read it; only an account that has genuinely
# become opsuser (via Hop 1) can.
chown opsuser:opsuser "$SHOP_ROOT/backups/diagnostics/rootwatch.core"
chmod 440 "$SHOP_ROOT/backups/diagnostics/rootwatch.core"

echo "[privesc-setup] writing flags"
echo "AI-LAB{stage1_appuser_code_execution_via_thumbnail_command_injection}" > "$SHOP_ROOT/flags/stage1"
chown appuser:appuser "$SHOP_ROOT/flags/stage1"
chmod 440 "$SHOP_ROOT/flags/stage1"

echo "AI-LAB{stage2_opsuser_via_python_import_path_hijack_and_self_signed_manifest}" > "$SHOP_ROOT/flags/stage2"
chown opsuser:opsuser "$SHOP_ROOT/flags/stage2"
chmod 440 "$SHOP_ROOT/flags/stage2"

echo "AI-LAB{root_via_rootwatch_coredump_aesgcm_key_recovery}" > /root/final_flag
chown root:root /root/final_flag
chmod 600 /root/final_flag

echo "[privesc-setup] fixing ownership of app tree"
chown -R appuser:appuser "$SHOP_ROOT/uploads" "$SHOP_ROOT/media" "$SHOP_ROOT/database" "$SHOP_ROOT/logs" 2>/dev/null || true

echo "[privesc-setup] restricting provisioning sources to root (not attacker-readable)"
# These files are only needed at build time and by a root-run reset; the app
# never reads them at runtime. Locking them to root keeps a foothold account
# from reading the provisioning scripts/sources directly off disk.
chown -R root:root "$SHOP_ROOT/vulnerable" 2>/dev/null || true
chmod -R go-rwx "$SHOP_ROOT/vulnerable" 2>/dev/null || true

echo "[privesc-setup] done"
