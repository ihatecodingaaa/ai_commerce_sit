"""Verifies the deterministic two-hop privilege-escalation misconfiguration
(appuser -> opsuser -> root, no group membership involved in either hop).

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
BACKUP_SCRIPT = BASE_DIR / "vulnerable" / "privilege_escalation" / "backup.sh"
SETUP_SCRIPT = BASE_DIR / "vulnerable" / "privilege_escalation" / "setup_privesc.sh"


def test_no_blanket_sudo_rule_anywhere_in_repo():
    """The lab must never grant ALL=(ALL) NOPASSWD:ALL -- the escalation
    path has to be discovered, not handed out."""
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "ALL=(ALL) NOPASSWD:ALL" not in text
    assert "ALL=(ALL) NOPASSWD: ALL" not in text


def test_sudo_rule_is_scoped_to_opsuser_and_backup_script_only():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh" in text


def test_no_group_based_privilege_grant_remains():
    """The old design (appuser in a shopops group that group-write-owned
    the sudo target) must be fully gone -- both hops are now individual
    account boundaries, not shared group membership."""
    setup_text = SETUP_SCRIPT.read_text(encoding="utf-8")
    backup_text = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "shopops" not in setup_text
    assert "shopops" not in backup_text
    assert "appuser ALL=" not in setup_text  # appuser has no sudo rule at all now


def test_backup_script_exists_and_is_shell():
    assert BACKUP_SCRIPT.exists()
    assert BACKUP_SCRIPT.read_text(encoding="utf-8").startswith("#!/bin/bash")


def test_backup_script_installed_mode_is_not_group_or_world_writable():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'install -m 750 -o root -g root "$SCRIPT_DIR/backup.sh"' in text


def test_backup_script_uses_bare_glob_tar_over_opsuser_writable_staging_dir():
    """This is the actual Hop 2 bug: a wildcard passed to tar over a
    directory the sudo-permitted account can write to."""
    text = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "STAGING_DIR" in text
    assert "cd \"$STAGING_DIR\"" in text
    assert 'tar -czf "$BACKUP_DIR/shop-backup-$TS.tar.gz" *' in text


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/backup.sh").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_backup_script_is_root_owned_and_not_writable_by_others():
    path = Path("/opt/shop/scripts/backup.sh")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IWGRP), "backup.sh must not be group-writable (the old bug is fixed)"
    assert not (mode & stat.S_IWOTH), "backup.sh must not be world-writable"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/logs/provisioning.log").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_provisioning_log_is_world_readable():
    """The Hop 1 bug is intentional: this file leaking opsuser's password
    to any local account is exactly what the student is meant to find."""
    path = Path("/opt/shop/logs/provisioning.log")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert mode & stat.S_IROTH, "provisioning.log should be world-readable (the intentional bug)"
    content = path.read_text(encoding="utf-8")
    assert "opsuser" in content and "password" in content.lower()


@pytest.mark.skipif(
    os.name != "posix" or subprocess.run(["id", "-u", "opsuser"], capture_output=True).returncode != 0,
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_opsuser_staging_dir_not_writable_by_appuser():
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
