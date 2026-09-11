#!/bin/bash
# Provisions the deterministic local privilege-escalation misconfiguration
# inside the app container. Run as root, once at image build time and again
# by scripts/reset_lab.sh to restore the vulnerable state after a student
# (deliberately or accidentally) breaks it.
#
# Misconfiguration summary (see docs for the full writeup):
#   1. appuser is a member of group `shopops`.
#   2. /opt/shop/scripts/backup.sh is owned by root:shopops, mode 774
#      (group-writable).
#   3. /etc/sudoers.d/shop-backup lets appuser run EXACTLY that script as
#      root with NOPASSWD -- not a blanket ALL=(ALL) rule.
#   4. appuser can therefore edit backup.sh (group write) and then
#      `sudo /opt/shop/scripts/backup.sh` to run their edit as root.
#
# This is a configuration bug, not a kernel exploit, and is fully
# reproducible after every reset.
set -euo pipefail

SHOP_ROOT="/opt/shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[privesc-setup] provisioning appuser / shopops group"
getent group shopops >/dev/null || groupadd shopops
id -u appuser >/dev/null 2>&1 || useradd -m -s /bin/bash -g shopops appuser

echo "[privesc-setup] laying out $SHOP_ROOT"
mkdir -p "$SHOP_ROOT/scripts" "$SHOP_ROOT/backups" "$SHOP_ROOT/flags" "$SHOP_ROOT/uploads/images" \
         "$SHOP_ROOT/media/product_photos" "$SHOP_ROOT/database" "$SHOP_ROOT/logs"

echo "[privesc-setup] installing backup.sh with the deliberate group-write bug"
install -m 774 -o root -g shopops "$SCRIPT_DIR/backup.sh" "$SHOP_ROOT/scripts/backup.sh"
chown root:shopops "$SHOP_ROOT/scripts/backup.sh"
chmod 774 "$SHOP_ROOT/scripts/backup.sh"

echo "[privesc-setup] installing scoped NOPASSWD sudo rule"
cat > /etc/sudoers.d/shop-backup <<'EOF'
appuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh
EOF
chmod 440 /etc/sudoers.d/shop-backup
visudo -cf /etc/sudoers.d/shop-backup

echo "[privesc-setup] writing flags"
echo "AI-LAB{stage1_appuser_code_execution_via_image_upload_plugin}" > "$SHOP_ROOT/flags/stage1"
chown appuser:shopops "$SHOP_ROOT/flags/stage1"
chmod 440 "$SHOP_ROOT/flags/stage1"

echo "AI-LAB{stage2_group_writable_root_script_found}" > "$SHOP_ROOT/flags/stage2"
chown root:shopops "$SHOP_ROOT/flags/stage2"
chmod 440 "$SHOP_ROOT/flags/stage2"

echo "AI-LAB{root_via_sudo_group_writable_script_privesc}" > /root/final_flag
chown root:root /root/final_flag
chmod 600 /root/final_flag

echo "[privesc-setup] fixing ownership of app tree"
chown -R appuser:shopops "$SHOP_ROOT/uploads" "$SHOP_ROOT/media" "$SHOP_ROOT/database" "$SHOP_ROOT/logs" "$SHOP_ROOT/backups" 2>/dev/null || true

echo "[privesc-setup] done"
