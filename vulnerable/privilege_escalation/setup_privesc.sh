#!/bin/bash
# Provisions the deterministic local privilege-escalation misconfiguration
# inside the app container. Run as root, once at image build time and again
# by scripts/reset_lab.sh to restore the vulnerable state after a student
# (deliberately or accidentally) breaks it.
#
# Two-hop chain, each hop a different bug class -- no group membership is
# involved anywhere in either hop:
#
#   Hop 1 (appuser -> opsuser): a misplaced credential. opsuser's password
#   is generated at provisioning time and then pasted into a world-readable
#   provisioning log, exactly the "secret got logged/pasted somewhere it
#   never should have been" mistake this lab also teaches at the database
#   layer (see database/seed.py's INC-10485 ticket). appuser can read the
#   log and `su opsuser` with the leaked password.
#
#   Hop 2 (opsuser -> root): a tar wildcard/argument injection. opsuser has
#   a scoped NOPASSWD sudo rule for exactly one script (backup.sh), which
#   is root-owned and NOT writable by opsuser -- the old group-writable bug
#   is gone. The bug instead lives inside the script's `tar -czf dest *`
#   invocation over a directory opsuser can write to. See backup.sh and
#   README.md for the full writeup.
set -euo pipefail

SHOP_ROOT="/opt/shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[privesc-setup] provisioning appuser (low) and opsuser (mid) accounts"
id -u appuser >/dev/null 2>&1 || useradd -m -s /bin/bash appuser
id -u opsuser >/dev/null 2>&1 || useradd -m -s /bin/bash opsuser

# opsuser's password is regenerated on every provision/reset, the same
# idiom as the catalog-sync-service token and the admin-account password in
# database/seed.py -- it has to actually be discovered via the leaked log
# below, not be a fixed, guessable constant. Generated via python3 (already
# a hard dependency of this image) rather than /dev/urandom piped through
# tr/head, which is prone to SIGPIPE failures under `set -o pipefail`.
OPSUSER_PASSWORD="ops-$(python3 -c 'import secrets; print(secrets.token_urlsafe(10))')"
echo "opsuser:${OPSUSER_PASSWORD}" | chpasswd

echo "[privesc-setup] laying out $SHOP_ROOT"
mkdir -p "$SHOP_ROOT/scripts" "$SHOP_ROOT/backups" "$SHOP_ROOT/backups/staging" "$SHOP_ROOT/flags" \
         "$SHOP_ROOT/uploads/images" "$SHOP_ROOT/media/product_photos" "$SHOP_ROOT/database" "$SHOP_ROOT/logs"

echo "[privesc-setup] writing the misplaced-credential provisioning log (world-readable -- the Hop 1 bug)"
cat > "$SHOP_ROOT/logs/provisioning.log" <<EOF
[provision] created appuser account to run the shop-lab app process
[provision] created opsuser account for scheduled maintenance/backup tasks
[provision] opsuser initial password: ${OPSUSER_PASSWORD} (TODO rotate before go-live -- OPS-4471)
[provision] opsuser granted scoped sudo rule for /opt/shop/scripts/backup.sh only
[provision] provisioning complete
EOF
chown root:root "$SHOP_ROOT/logs/provisioning.log"
chmod 644 "$SHOP_ROOT/logs/provisioning.log"

echo "[privesc-setup] preparing opsuser-writable staging dir for backup.sh"
touch "$SHOP_ROOT/backups/staging/.placeholder"
chown -R opsuser:opsuser "$SHOP_ROOT/backups/staging"
chmod 700 "$SHOP_ROOT/backups/staging"

echo "[privesc-setup] installing backup.sh, root-owned and NOT writable by opsuser"
install -m 750 -o root -g root "$SCRIPT_DIR/backup.sh" "$SHOP_ROOT/scripts/backup.sh"

echo "[privesc-setup] installing sudo rule scoped to opsuser only"
rm -f /etc/sudoers.d/shop-backup  # remove any leftover rule from the old group-based design
cat > /etc/sudoers.d/shop-ops <<'EOF'
opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh
EOF
chmod 440 /etc/sudoers.d/shop-ops
visudo -cf /etc/sudoers.d/shop-ops

echo "[privesc-setup] writing flags"
echo "AI-LAB{stage1_appuser_code_execution_via_image_upload_plugin}" > "$SHOP_ROOT/flags/stage1"
chown appuser:appuser "$SHOP_ROOT/flags/stage1"
chmod 440 "$SHOP_ROOT/flags/stage1"

echo "AI-LAB{stage2_opsuser_via_leaked_password_in_provisioning_log}" > "$SHOP_ROOT/flags/stage2"
chown opsuser:opsuser "$SHOP_ROOT/flags/stage2"
chmod 440 "$SHOP_ROOT/flags/stage2"

echo "AI-LAB{root_via_sudo_tar_wildcard_injection}" > /root/final_flag
chown root:root /root/final_flag
chmod 600 /root/final_flag

echo "[privesc-setup] fixing ownership of app tree"
chown -R appuser:appuser "$SHOP_ROOT/uploads" "$SHOP_ROOT/media" "$SHOP_ROOT/database" "$SHOP_ROOT/logs" 2>/dev/null || true
# provisioning.log must stay world-readable (the deliberate bug) even after
# the recursive chown above targets the rest of logs/ at appuser.
chown root:root "$SHOP_ROOT/logs/provisioning.log"
chmod 644 "$SHOP_ROOT/logs/provisioning.log"

echo "[privesc-setup] done"
