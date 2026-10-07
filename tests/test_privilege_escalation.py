"""Verifies the deterministic, single-path, three-tier privilege-escalation
chain (appuser -> opsuser -> root). Hop 1 (appuser -> opsuser) is a Python
import-path hijack gated by a self-signed integrity check; Hop 2
(opsuser -> root) has NO sudo grant at all and is instead AES-256-GCM
credential recovery from a deliberately-crashed process's core dump.

The live filesystem/account checks only make sense inside the app Docker
container (or a Linux host where setup_privesc.sh has actually been run as
root) -- they're skipped everywhere else. The static checks (script/setup
content, no ALL=(ALL) NOPASSWD:ALL anywhere, no group-based rule, no sudo
rule for opsuser at all) run unconditionally and are what CI/non-Linux dev
machines exercise.
"""
import os
import stat
import subprocess
from pathlib import Path

import pytest


def _exists_even_if_unreadable(path):
    """Path.exists() raises PermissionError instead of returning False when
    a parent directory (e.g. /root, mode 700) blocks traversal -- which is
    exactly the case for an unprivileged test runner checking a root-only
    path. Treat "can't even see it" the same as "not there yet": skip
    rather than error."""
    try:
        return path.exists()
    except PermissionError:
        return False

BASE_DIR = Path(__file__).resolve().parent.parent
PRIVESC_DIR = BASE_DIR / "vulnerable" / "privilege_escalation"
ARCHIVE_WORKER = PRIVESC_DIR / "archive_worker.py"
ROOTWATCH_C = PRIVESC_DIR / "rootwatch.c"
GEN_ROOT_SECRET = PRIVESC_DIR / "gen_root_secret.py"
SETUP_SCRIPT = PRIVESC_DIR / "setup_privesc.sh"


def test_no_blanket_sudo_rule_anywhere_in_repo():
    """The lab must never grant ALL=(ALL) NOPASSWD:ALL -- the escalation
    path has to be discovered, not handed out."""
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "ALL=(ALL) NOPASSWD:ALL" not in text
    assert "ALL=(ALL) NOPASSWD: ALL" not in text


def test_hop1_sudo_rule_is_scoped_to_exactly_one_script():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *" in text
    assert text.count("appuser ALL=") == 1


def test_opsuser_has_no_sudo_rule_at_all():
    """Hop 2 is deliberately not a sudo-trust-boundary bug -- opsuser
    should have zero sudo grants anywhere in the provisioning script."""
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "opsuser ALL=" not in text
    # setup_privesc.sh removes any stale /etc/sudoers.d/shop-ops left over
    # from a prior design, it never installs one -- that line must be an
    # `rm`, not a sudoers rule definition.
    assert 'rm -f /etc/sudoers.d/shop-ops' in text


def test_no_group_based_privilege_grant_remains():
    """No shared group membership grants privilege anywhere in this chain
    -- each hop is an individual account boundary."""
    setup_text = SETUP_SCRIPT.read_text(encoding="utf-8")
    worker_text = ARCHIVE_WORKER.read_text(encoding="utf-8")
    rootwatch_text = ROOTWATCH_C.read_text(encoding="utf-8")
    assert "shopops" not in setup_text
    assert "shopops" not in worker_text
    assert "shopops" not in rootwatch_text


def test_opsuser_account_is_locked_no_password_route():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "usermod -L opsuser" in text


def test_archive_worker_exists_and_is_python():
    assert ARCHIVE_WORKER.exists()
    assert ARCHIVE_WORKER.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_rootwatch_source_exists_and_is_c():
    assert ROOTWATCH_C.exists()
    text = ROOTWATCH_C.read_text(encoding="utf-8")
    assert "#include <openssl/evp.h>" in text


def test_gen_root_secret_exists_and_is_python():
    assert GEN_ROOT_SECRET.exists()
    assert GEN_ROOT_SECRET.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_archive_worker_installed_root_owned_not_writable_by_others():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'install -m 755 -o root -g root "$SCRIPT_DIR/archive_worker.py"' in text


def test_archive_worker_inserts_writable_dir_into_search_path():
    """This is the actual Hop 1 bug: an appuser-writable directory is
    inserted into sys.path before a name-based import (CWE-427)."""
    text = ARCHIVE_WORKER.read_text(encoding="utf-8")
    assert "sys.path.insert(0, OUTBOX_DIR)" in text
    assert "__import__(handler_name)" in text


def test_archive_worker_integrity_check_is_self_defeating():
    """Hop 1's compounding bug (CWE-354): the manifest that's supposed to
    gate the import lives in the same appuser-writable OUTBOX_DIR as the
    handler modules themselves."""
    text = ARCHIVE_WORKER.read_text(encoding="utf-8")
    assert "MANIFEST_PATH" in text
    assert "handlers.manifest" in text
    assert "hashlib.sha256" in text
    # the manifest path must be derived from OUTBOX_DIR, not some other,
    # better-protected location
    assert 'MANIFEST_PATH = f"{OUTBOX_DIR}/handlers.manifest"' in text


def test_outbox_dir_owned_by_appuser_not_opsuser():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'chown -R appuser:appuser "$SHOP_ROOT/backups/outbox"' in text


def test_handlers_manifest_seeded_in_appuser_writable_outbox():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "handlers.manifest" in text
    assert 'chown appuser:appuser "$SHOP_ROOT/backups/outbox/noop.py" "$SHOP_ROOT/backups/outbox/handlers.manifest"' in text


def test_rootwatch_decrypts_with_aes_256_gcm():
    text = ROOTWATCH_C.read_text(encoding="utf-8")
    assert "EVP_aes_256_gcm()" in text
    assert "EVP_CTRL_GCM_SET_TAG" in text


def test_rootwatch_scrubs_plaintext_but_never_key_or_blob():
    """This is the actual Hop 2 bug, precisely: `plaintext` (the decrypted
    password -- the variable that "looks like" the secret) IS correctly
    cleansed before the deliberate abort(), which closes off a trivial
    `strings`-only shortcut. `key` and `blob` (nonce || ciphertext || tag)
    -- exactly as sensitive, since together they reconstruct the password
    -- are never scrubbed at all, so a real AES-256-GCM decrypt is the
    only way to recover it from the resulting core dump."""
    text = ROOTWATCH_C.read_text(encoding="utf-8")
    assert "abort();" in text
    assert "OPENSSL_cleanse(plaintext, sizeof(plaintext));" in text
    for unsafe in ("OPENSSL_cleanse(key", "OPENSSL_cleanse(blob",
                   "memset(key", "memset(blob",
                   "explicit_bzero(key", "explicit_bzero(blob"):
        assert unsafe not in text, f"key/blob must never be scrubbed -- found {unsafe!r}"


def test_root_secret_key_and_blob_generated_and_locked_down():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "gen_root_secret.py" in text
    assert 'chmod 600 "$ROOTWATCH_DIR/root_secret.key" "$ROOTWATCH_DIR/root_secret.enc"' in text
    assert 'chown root:root "$ROOTWATCH_DIR/root_secret.key" "$ROOTWATCH_DIR/root_secret.enc"' in text


def test_rootwatch_binary_compiled_root_owned():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'gcc -O0 -g -o "$ROOTWATCH_DIR/rootwatch" "$SCRIPT_DIR/rootwatch.c" -lcrypto' in text
    assert 'chown root:root "$ROOTWATCH_DIR/rootwatch"' in text


def test_core_dump_captured_via_gdb_and_owned_by_opsuser():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "generate-core-file" in text
    assert 'chown opsuser:opsuser "$SHOP_ROOT/backups/diagnostics/rootwatch.core"' in text
    assert 'chmod 440 "$SHOP_ROOT/backups/diagnostics/rootwatch.core"' in text


def test_scripts_directory_installed_not_writable_by_non_root():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'chmod 755 "$SHOP_ROOT/scripts"' in text


def test_password_is_actually_set_on_root_account():
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'echo "root:${ROOT_PASSWORD}" | chpasswd' in text


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/archive_worker.py").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_archive_worker_is_root_owned_and_not_writable_by_others():
    path = Path("/opt/shop/scripts/archive_worker.py")
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert not (mode & stat.S_IWGRP), "archive_worker.py must not be group-writable"
    assert not (mode & stat.S_IWOTH), "archive_worker.py must not be world-writable"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/backups/outbox/handlers.manifest").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_handlers_manifest_owned_by_appuser():
    import pwd
    path = Path("/opt/shop/backups/outbox/handlers.manifest")
    st = path.stat()
    owner = pwd.getpwuid(st.st_uid).pw_name
    assert owner == "appuser", "handlers.manifest must be appuser-owned -- that's the Hop 1 add-on bug"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/scripts/rootwatch/root_secret.key").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_root_secret_files_not_readable_by_non_root():
    for name in ("root_secret.key", "root_secret.enc"):
        path = Path("/opt/shop/scripts/rootwatch") / name
        st = path.stat()
        mode = stat.S_IMODE(st.st_mode)
        assert not (mode & stat.S_IRGRP), f"{name} must not be group-readable"
        assert not (mode & stat.S_IROTH), f"{name} must not be world-readable"


@pytest.mark.skipif(
    os.name != "posix" or not Path("/opt/shop/backups/diagnostics/rootwatch.core").exists(),
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_core_dump_owned_by_opsuser_not_readable_by_others():
    """Mode 440 here (like flags/stage1 and flags/stage2) is intentional,
    not a leak: setup_privesc.sh creates `opsuser` with a dedicated,
    single-member primary group of the same name (standard `useradd`
    behaviour, verified below), so group-readable is exactly as private
    as owner-only -- nobody but opsuser is ever in that group. What
    actually matters, and what must never regress, is that it isn't
    world-readable and that its owning group really does have no other
    members."""
    import grp
    import pwd
    path = Path("/opt/shop/backups/diagnostics/rootwatch.core")
    st = path.stat()
    owner = pwd.getpwuid(st.st_uid).pw_name
    group = grp.getgrgid(st.st_gid)
    mode = stat.S_IMODE(st.st_mode)
    assert owner == "opsuser", "rootwatch.core must be opsuser-owned -- that's the Hop 2 bug"
    assert group.gr_name == "opsuser", "must be owned by opsuser's own dedicated group"
    assert group.gr_mem == [], "opsuser's group must have no other members, or group-read leaks it"
    assert not (mode & stat.S_IROTH), "rootwatch.core must not be world-readable"


@pytest.mark.skipif(
    os.name != "posix"
    or os.geteuid() != 0
    or subprocess.run(["id", "-u", "opsuser"], capture_output=True).returncode != 0,
    reason="requires the provisioned lab container, run as root "
    "(passwd -S on another account refuses outright for a non-root caller, "
    "which would otherwise read as a false failure here, not a skip)",
)
def test_live_opsuser_has_no_valid_password():
    result = subprocess.run(["passwd", "-S", "opsuser"], capture_output=True, text=True)
    status = result.stdout.split()
    assert len(status) >= 2, f"passwd -S opsuser produced no usable output: {result!r}"
    assert status[1] in ("L", "LK"), f"opsuser must have no usable password, got status {status[1]!r}"


@pytest.mark.skipif(
    os.name != "posix" or subprocess.run(["id", "-u", "opsuser"], capture_output=True).returncode != 0,
    reason="requires the provisioned lab container (run inside Docker as root)",
)
def test_live_opsuser_has_no_sudo_rule():
    result = subprocess.run(
        ["sudo", "-l", "-U", "opsuser"], capture_output=True, text=True
    )
    combined = (result.stdout + result.stderr).lower()
    assert "not allowed to run sudo" in combined or "user opsuser may run" not in combined


@pytest.mark.skipif(
    os.name != "posix" or not _exists_even_if_unreadable(Path("/root/final_flag")),
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
