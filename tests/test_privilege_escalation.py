"""Verifies the deterministic, single-path, three-tier privilege-escalation
chain (appuser -> opsuser -> root). Each hop must have exactly one sudo
grant and no alternate/group-based route.

The live filesystem/account checks only make sense inside the app Docker
container (or a Linux host where setup_privesc.sh has actually been run as
root) -- they're skipped everywhere else. The static checks (script/setup
content, no ALL=(ALL) NOPASSWD:ALL anywhere, no group-based rule) run
unconditionally and are what CI/non-Linux dev machines exercise.
"""
import os
import stat
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
PRIVESC_DIR = BASE_DIR / "vulnerable" / "privilege_escalation"
BACKUP_SCRIPT = PRIVESC_DIR / "backup.sh"
EXPORT_SCRIPT = PRIVESC_DIR / "ticket_export.py"
SETUP_SCRIPT = PRIVESC_DIR / "setup_privesc.sh"


def test_no_blanket_sudo_rule_anywhere_in_repo():
    """The lab must never grant ALL=(ALL) NOPASSWD:ALL -- the escalation
    path has to be discovered, not handed out."""
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "ALL=(ALL) NOPASSWD:ALL" not in text
    assert "ALL=(ALL) NOPASSWD: ALL" not in text


def test_hop1_sudo_rule_is_scoped_to_exactly_one_script():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/ticket_export.py *" in text
    # appuser must have no other sudo grant anywhere in the provisioning script
    assert text.count("appuser ALL=") == 1


def test_hop2_sudo_rule_is_scoped_to_exactly_one_script():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh" in text
    assert text.count("opsuser ALL=") == 1


def test_no_group_based_privilege_grant_remains():
    """The old design (a shared group that group-write-owned the sudo
    target) must be fully gone -- each hop is an individual account
    boundary, not shared group membership."""
    setup_text = SETUP_SCRIPT.read_text(encoding="utf-8")
    backup_text = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "shopops" not in setup_text
    assert "shopops" not in backup_text


def test_opsuser_account_is_locked_no_password_route():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "usermod -L opsuser" in text


def test_backup_script_exists_and_is_shell():
    assert BACKUP_SCRIPT.exists()
    assert BACKUP_SCRIPT.read_text(encoding="utf-8").startswith("#!/bin/bash")


def test_ticket_export_script_exists_and_is_python():
    assert EXPORT_SCRIPT.exists()
    assert EXPORT_SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_both_scripts_installed_root_owned_not_writable_by_others():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'install -m 755 -o root -g root "$SCRIPT_DIR/ticket_export.py"' in text
    assert 'install -m 755 -o root -g root "$SCRIPT_DIR/backup.sh"' in text


def test_ticket_export_uses_pickle_load_on_argv():
    """This is the actual Hop 1 bug: unvalidated deserialization of a
    caller-supplied file path."""
    text = EXPORT_SCRIPT.read_text(encoding="utf-8")
    assert "pickle.load(" in text
    assert "sys.argv[1]" in text


def test_backup_script_uses_bare_glob_tar_over_opsuser_writable_staging_dir():
    """This is the actual Hop 2 bug: a wildcard passed to tar over a
    directory the sudo-permitted account can write to."""
    text = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "STAGING_DIR" in text
    assert "cd \"$STAGING_DIR\"" in text
    assert 'tar -czf "$BACKUP_DIR/shop-backup-$TS.tar.gz" *' in text


def test_scripts_directory_installed_not_writable_by_non_root():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'chmod 755 "$SHOP_ROOT/scripts"' in text


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/backup.sh").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_backup_script_is_root_owned_and_not_writable_by_others():
    path = Path("/opt/shop/scripts/backup.sh")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IWGRP), "backup.sh must not be group-writable"
    assert not (mode & stat.S_IWOTH), "backup.sh must not be world-writable"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/ticket_export.py").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_ticket_export_is_root_owned_and_not_writable_by_others():
    path = Path("/opt/shop/scripts/ticket_export.py")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IWGRP), "ticket_export.py must not be group-writable"
    assert not (mode & stat.S_IWOTH), "ticket_export.py must not be world-writable"


@pytest.mark.skipif(
    os.name != "posix" or subprocess.run(["id", "-u", "opsuser"], capture_output=True).returncode != 0,
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_opsuser_has_no_valid_password():
    result = subprocess.run(["passwd", "-S", "opsuser"], capture_output=True, text=True)
    # passwd -S prints a status field: L (locked) or LK -- never P (usable password)
    status = result.stdout.split()
    assert len(status) >= 2
    assert status[1] in ("L", "LK"), f"opsuser must have no usable password, got status {status[1]!r}"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/backups/staging").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_opsuser_staging_dir_not_writable_by_others():
    path = Path("/opt/shop/backups/staging")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IWOTH), "staging dir must not be world-writable"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/root/final_flag").exists(),
    reason="requires root access inside the provisioned lab container",
)
def test_live_root_flag_is_root_only_readable():
    path = Path("/root/final_flag")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IROTH), "final flag must not be world-readable"
    content = path.read_text(encoding="utf-8").strip()
    assert content.startswith("AI-LAB{")


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/flags/stage2").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_stage2_flag_not_readable_by_appuser():
    """stage2 proves the Hop 1 -> Hop 2 transition specifically: readable
    by opsuser/root only, not by the low-priv appuser account."""
    path = Path("/opt/shop/flags/stage2")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IROTH), "stage2 flag must not be world-readable"
