#!/bin/bash
# ShopLite maintenance backup script.
#
# Intended purpose: archive staged backup files so an on-call engineer
# (opsuser) can run it without needing full root. Installed with a
# NOPASSWD sudo rule scoped to exactly this script, granted to opsuser
# (see vulnerable/privilege_escalation/setup_privesc.sh) -- NOT a blanket
# `ALL=(ALL) NOPASSWD:ALL` rule, and this file itself is root-owned,
# mode 750 -- opsuser cannot edit it.
#
# THE BUG (intentional, for training): CWE-88-style tar wildcard/argument
# injection (a well-known GTFOBins technique), not a file-permission bug.
# This script cd's into a directory opsuser legitimately owns and writes
# to (STAGING_DIR) and archives it with a bare `tar -czf <dest> *`. Because
# the shell -- not tar -- expands that `*` glob, opsuser can plant
# filenames in STAGING_DIR that tar's argument parser will interpret as
# flags instead of file names, e.g. `--checkpoint=1` and
# `--checkpoint-action=exec=sh payload.sh`. When root's sudo'd tar
# expands the glob, those "filenames" become extra tar arguments and tar
# runs the attacker's script as root. See
# vulnerable/privilege_escalation/README.md for the full writeup and the
# exact reproduction steps.
set -e

STAGING_DIR="/opt/shop/backups/staging"
BACKUP_DIR="/opt/shop/backups"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$STAGING_DIR" "$BACKUP_DIR"
cd "$STAGING_DIR"
tar -czf "$BACKUP_DIR/shop-backup-$TS.tar.gz" *

echo "Backup written to $BACKUP_DIR/shop-backup-$TS.tar.gz"
