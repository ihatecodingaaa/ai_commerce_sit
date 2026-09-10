"""Verifies the deterministic privilege-escalation misconfiguration.

The live filesystem checks only make sense inside the app Docker container
(or a Linux host where setup_privesc.sh has actually been run as root) --
they're skipped everywhere else. The static checks (script content, no
ALL=(ALL) NOPASSWD:ALL anywhere) run unconditionally and are what CI/non-
Linux dev machines exercise.
"""
import os
import stat
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


def test_sudo_rule_is_scoped_to_backup_script_only():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "appuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh" in text


def test_backup_script_exists_and_is_shell():
    assert BACKUP_SCRIPT.exists()
    assert BACKUP_SCRIPT.read_text(encoding="utf-8").startswith("#!/bin/bash")


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/backup.sh").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_backup_script_is_group_writable_by_shopops():
    path = Path("/opt/shop/scripts/backup.sh")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert mode & stat.S_IWGRP, "backup.sh should be group-writable (the intentional bug)"


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
