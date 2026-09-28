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
#   writable by appuser (CWE-427, uncontrolled search path element) --
#   appuser plants a malicious handler module and gets arbitrary code
#   execution as opsuser. opsuser has no password at all (the account is
#   locked), so this exploit is the *only* way to become opsuser.
#
#   Hop 2 (opsuser -> root): opsuser has exactly one sudo grant --
#   NOPASSWD to run backup.sh as root, nothing else, and cannot edit that
#   script (root-owned, mode 755). The script sources a config file
#   (backup.conf) that opsuser DOES own and can edit, then `eval`s
#   whatever POST_BACKUP_HOOK command that file names, as root -- a
#   trusted process reading and blindly executing directives from a
#   lower-privileged account's configuration file.
#
# See archive_worker.py, backup.sh, and README.md for the full writeup.
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
mkdir -p "$SHOP_ROOT/scripts" "$SHOP_ROOT/backups" "$SHOP_ROOT/backups/outbox" "$SHOP_ROOT/flags" \
         "$SHOP_ROOT/uploads/images" "$SHOP_ROOT/media/product_photos" "$SHOP_ROOT/database" "$SHOP_ROOT/logs"
# root-owned, not writable by appuser or opsuser -- neither script can be
# tampered with directly; the sudo-gated exploits are the only route in.
chown root:root "$SHOP_ROOT/scripts"
chmod 755 "$SHOP_ROOT/scripts"

echo "[privesc-setup] preparing appuser-writable outbox dir (Hop 1's search-path bug)"
touch "$SHOP_ROOT/backups/outbox/.placeholder"
chown -R appuser:appuser "$SHOP_ROOT/backups/outbox"
chmod 755 "$SHOP_ROOT/backups/outbox"  # world-readable/executable so opsuser's
                                        # import can read it -- only appuser can write

echo "[privesc-setup] installing archive_worker.py (Hop 1 target), root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/archive_worker.py" "$SHOP_ROOT/scripts/archive_worker.py"

echo "[privesc-setup] installing backup.sh (Hop 2 target), root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/backup.sh" "$SHOP_ROOT/scripts/backup.sh"

echo "[privesc-setup] installing backup.conf, opsuser-owned (Hop 2's actual bug)"
cat > "$SHOP_ROOT/scripts/backup.conf" <<'EOF'
# ShopLite backup notification hook.
# Uncomment and set POST_BACKUP_HOOK to run a command after each backup
# completes (e.g. to ping a monitoring endpoint).
# POST_BACKUP_HOOK="curl -fsS https://status.example.test/ping/backup"
EOF
chown opsuser:opsuser "$SHOP_ROOT/scripts/backup.conf"
chmod 644 "$SHOP_ROOT/scripts/backup.conf"

echo "[privesc-setup] installing sudo rules -- one per hop, nothing else"
cat > /etc/sudoers.d/shop-archive <<'EOF'
appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *
EOF
chmod 440 /etc/sudoers.d/shop-archive
visudo -cf /etc/sudoers.d/shop-archive

cat > /etc/sudoers.d/shop-ops <<'EOF'
opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh
EOF
chmod 440 /etc/sudoers.d/shop-ops
visudo -cf /etc/sudoers.d/shop-ops

echo "[privesc-setup] writing flags"
echo "AI-LAB{stage1_appuser_code_execution_via_thumbnail_command_injection}" > "$SHOP_ROOT/flags/stage1"
chown appuser:appuser "$SHOP_ROOT/flags/stage1"
chmod 440 "$SHOP_ROOT/flags/stage1"

echo "AI-LAB{stage2_opsuser_via_python_import_path_hijack}" > "$SHOP_ROOT/flags/stage2"
chown opsuser:opsuser "$SHOP_ROOT/flags/stage2"
chmod 440 "$SHOP_ROOT/flags/stage2"

echo "AI-LAB{root_via_backup_conf_hook_injection}" > /root/final_flag
chown root:root /root/final_flag
chmod 600 /root/final_flag

echo "[privesc-setup] fixing ownership of app tree"
chown -R appuser:appuser "$SHOP_ROOT/uploads" "$SHOP_ROOT/media" "$SHOP_ROOT/database" "$SHOP_ROOT/logs" 2>/dev/null || true

echo "[privesc-setup] done"
