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

echo "[privesc-setup] seeding handlers.manifest (Hop 1's broken integrity check -- appuser-writable, same dir)"
cat > "$SHOP_ROOT/backups/outbox/noop.py" <<'EOF'
"""Legitimate no-op archive handler -- does nothing."""
def archive():
    pass
EOF
NOOP_HASH="$(sha256sum "$SHOP_ROOT/backups/outbox/noop.py" | awk '{print $1}')"
cat > "$SHOP_ROOT/backups/outbox/handlers.manifest" <<EOF
{"noop": "$NOOP_HASH"}
EOF
chown appuser:appuser "$SHOP_ROOT/backups/outbox/noop.py" "$SHOP_ROOT/backups/outbox/handlers.manifest"

echo "[privesc-setup] installing archive_worker.py (Hop 1 target), root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/archive_worker.py" "$SHOP_ROOT/scripts/archive_worker.py"

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

echo "[privesc-setup] done"
