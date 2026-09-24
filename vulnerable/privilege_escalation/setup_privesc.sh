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
#   NOPASSWD to run ticket_export.py *as opsuser*, nothing else, and
#   cannot edit that script. The script insecurely unpickles whatever file
#   path it's given (CWE-502) -- appuser crafts a malicious pickle and
#   gets arbitrary code execution as opsuser. opsuser has no password at
#   all (the account is locked), so this exploit is the *only* way to
#   become opsuser -- there is nothing to brute-force or leak.
#
#   Hop 2 (opsuser -> root): opsuser has exactly one sudo grant --
#   NOPASSWD to run backup.sh as root, nothing else, and cannot edit that
#   script (root-owned, mode 755). The script runs a bare `tar -czf dest *`
#   over a directory opsuser owns -- a tar wildcard/argument injection
#   (GTFOBins-style) gets root to execute opsuser's payload.
#
# See backup.sh, ticket_export.py, and README.md for the full writeup.
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
mkdir -p "$SHOP_ROOT/scripts" "$SHOP_ROOT/backups" "$SHOP_ROOT/backups/staging" "$SHOP_ROOT/flags" \
         "$SHOP_ROOT/uploads/images" "$SHOP_ROOT/media/product_photos" "$SHOP_ROOT/database" "$SHOP_ROOT/logs"
# root-owned, not writable by appuser or opsuser -- neither script can be
# tampered with directly; the sudo-gated exploits are the only route in.
chown root:root "$SHOP_ROOT/scripts"
chmod 755 "$SHOP_ROOT/scripts"

echo "[privesc-setup] preparing opsuser-writable staging dir for backup.sh"
touch "$SHOP_ROOT/backups/staging/.placeholder"
chown -R opsuser:opsuser "$SHOP_ROOT/backups/staging"
chmod 700 "$SHOP_ROOT/backups/staging"

echo "[privesc-setup] installing ticket_export.py (Hop 1 target), root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/ticket_export.py" "$SHOP_ROOT/scripts/ticket_export.py"

echo "[privesc-setup] installing backup.sh (Hop 2 target), root-owned"
install -m 755 -o root -g root "$SCRIPT_DIR/backup.sh" "$SHOP_ROOT/scripts/backup.sh"

echo "[privesc-setup] installing sudo rules -- one per hop, nothing else"
cat > /etc/sudoers.d/shop-export <<'EOF'
appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/ticket_export.py *
EOF
chmod 440 /etc/sudoers.d/shop-export
visudo -cf /etc/sudoers.d/shop-export

cat > /etc/sudoers.d/shop-ops <<'EOF'
opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh
EOF
chmod 440 /etc/sudoers.d/shop-ops
visudo -cf /etc/sudoers.d/shop-ops

echo "[privesc-setup] writing flags"
echo "AI-LAB{stage1_appuser_code_execution_via_image_upload_plugin}" > "$SHOP_ROOT/flags/stage1"
chown appuser:appuser "$SHOP_ROOT/flags/stage1"
chmod 440 "$SHOP_ROOT/flags/stage1"

echo "AI-LAB{stage2_opsuser_via_pickle_deserialization_rce}" > "$SHOP_ROOT/flags/stage2"
chown opsuser:opsuser "$SHOP_ROOT/flags/stage2"
chmod 440 "$SHOP_ROOT/flags/stage2"

echo "AI-LAB{root_via_sudo_tar_wildcard_injection}" > /root/final_flag
chown root:root /root/final_flag
chmod 600 /root/final_flag

echo "[privesc-setup] fixing ownership of app tree"
chown -R appuser:appuser "$SHOP_ROOT/uploads" "$SHOP_ROOT/media" "$SHOP_ROOT/database" "$SHOP_ROOT/logs" 2>/dev/null || true

echo "[privesc-setup] done"
