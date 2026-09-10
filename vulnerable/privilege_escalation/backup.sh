#!/bin/bash
# ShopLite maintenance backup script.
#
# Intended purpose: archive the app database and uploaded images so an
# on-call engineer can run it without needing full root. Installed with a
# NOPASSWD sudo rule scoped to exactly this script (see
# vulnerable/privilege_escalation/setup_privesc.sh) -- NOT a blanket
# `ALL=(ALL) NOPASSWD:ALL` rule.
#
# THE BUG (intentional, for training): this file is owned by root but is
# GROUP-WRITABLE, and the application user is a member of that group. A
# script that sudo will run as root must never be writable by the account
# permitted to sudo-run it -- whoever can edit this file can make root run
# anything they want. See vulnerable/privilege_escalation/README.md.
set -e

BACKUP_DIR="/opt/shop/backups"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/shop-backup-$TS.tar.gz" \
    -C /opt/shop database uploads 2>/dev/null || true

echo "Backup written to $BACKUP_DIR/shop-backup-$TS.tar.gz"
