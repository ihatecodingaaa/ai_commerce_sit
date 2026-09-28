#!/bin/bash
# ShopLite maintenance backup script.
#
# Intended purpose: archive the app database and uploaded images, and
# optionally run a notification hook afterward (e.g. to ping a monitoring
# endpoint) configured via backup.conf. Installed with a NOPASSWD sudo
# rule scoped to exactly this script, granted to opsuser only (see
# vulnerable/privilege_escalation/setup_privesc.sh) -- NOT a blanket
# `ALL=(ALL) NOPASSWD:ALL` rule, and this file itself is root-owned, mode
# 755 -- opsuser cannot edit it.
#
# THE BUG (intentional, for training): this script sources a configuration
# file that opsuser -- the very account permitted to sudo-run this script
# -- owns and can freely edit, then executes whatever command that config
# names, unvalidated, as root. A scoped sudo rule and a non-writable
# script are NOT sufficient on their own if the privileged script trusts a
# lower-privileged account's configuration file. This mirrors a common
# real-world pattern: CI pipeline configs, git hooks, provisioner
# "run this command" blocks, and countless internal tools all read a
# config file for a command to execute, and mixing that with a privilege
# boundary is exactly this bug.
set -e

BACKUP_DIR="/opt/shop/backups"
CONF_FILE="/opt/shop/scripts/backup.conf"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/shop-backup-$TS.tar.gz" \
    -C /opt/shop database uploads 2>/dev/null || true
echo "Backup written to $BACKUP_DIR/shop-backup-$TS.tar.gz"

if [ -f "$CONF_FILE" ]; then
    # shellcheck disable=SC1090
    source "$CONF_FILE"
    if [ -n "${POST_BACKUP_HOOK:-}" ]; then
        echo "Running post-backup hook..."
        eval "$POST_BACKUP_HOOK"  # <-- THE BUG: opsuser fully controls this
    fi
fi
