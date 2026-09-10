# SECURITY.md — read this before deploying shop-lab anywhere

shop-lab is an **intentionally vulnerable educational application**. It
exists to teach a realistic AI-agent trust-boundary attack chain ending in
local privilege escalation to root. That means, by design, it contains:

- an indirect prompt-injection vulnerability in its RAG/knowledge-base
  retrieval path,
- a fake but real-looking internal service credential that is meant to be
  discovered and used,
- an unrestricted-file-upload vulnerability that leads to real code
  execution as an unprivileged application user, and
- a deterministic local privilege-escalation misconfiguration that leads
  to root, inside the app's own container.

## Isolation requirements — do not skip this

1. **Never expose this lab directly to the public Internet.** Run it only
   on a private/isolated network segment (a dedicated EC2 instance with a
   security group restricted to trusted IPs, a lab VPC, or a local
   machine). Anyone who can reach the app can execute code as `appuser` and
   escalate to root *inside its container* — don't let that be the general
   Internet.
2. **Use the Docker deployment for anything beyond local development.**
   The vulnerable privilege-escalation chain (Stages 8-12) is provisioned
   only inside the app container (`Dockerfile.app`,
   `vulnerable/privilege_escalation/`). The container has no bind mount
   into the host filesystem, no `docker.sock`, `--privileged`, or added
   capabilities — root obtained inside it stays inside it. Do not add any
   of those things to `docker-compose.yml`.
3. **Run it on a machine you're comfortable being fully compromised.**
   Treat the app container as "already rooted" from the moment it starts —
   because a student succeeding at the exercise is the intended outcome.
   Don't reuse the container/instance for anything else, and don't store
   unrelated data on the same host.
4. **Dedicate the EC2 instance to this lab.** Don't run other workloads on
   it. If you use the native (non-Docker) setup for developing Stages 1-7,
   note that it deliberately does **not** provision the
   privilege-escalation misconfiguration on the real host (see
   `scripts/setup.sh`) — that only happens inside Docker, on purpose.
5. **Reset between students/cohorts.** `scripts/reset_lab.sh` returns the
   lab to a known state, but a determined student who got a root shell in
   the container could in principle leave a persistent backdoor inside
   that container image's writable layers. For multi-cohort use, rebuild
   the container (`docker compose build --no-cache`) between groups rather
   than only running the reset script.

## No real secrets, ever

Every credential in this repository is a synthetic, fake, lab-only value:
the support-image-service token (randomly generated at seed time and
rotated automatically, never hardcoded -- see
app/services/credentials.py), the seeded user passwords, and `SECRET_KEY`.
If you fork or extend this lab:

- Never substitute a real AWS credential, API key, SSH key, or production
  secret for any of the placeholder values.
- Never point `OLLAMA_URL` at a shared/production Ollama instance.
- Never point `DATABASE_URL` at a real database.
- The final flag (`/root/final_flag`) and stage flags
  (`/opt/shop/flags/*`) are synthetic training strings (`AI-LAB{...}`),
  not real credentials, and contain no information about any real system.

## What the vulnerable upload/execution chain can and cannot do

- The code-execution primitive (Stage 8-9) only ever executes inside the
  app container's own Python process, writing only to
  `/opt/shop/uploads/images/` unless the payload itself chooses to write
  elsewhere on that container's filesystem (it has normal `appuser` file
  permissions, nothing more).
- There is no proxy, SSRF-style relay, or "fetch this URL for me" tool
  anywhere in the application that would let a student use this lab to
  attack a third-party host. The chatbot's tools only ever talk to the
  lab's own SQLite database and the lab's own Ollama instance over
  `OLLAMA_URL`.
- The privilege-escalation chain (Stage 10-11) is scoped to a single,
  narrow `sudo` rule against one script inside the container — never
  `ALL=(ALL) NOPASSWD:ALL`, and never anything reaching outside the
  container's own filesystem.

## Reporting problems with the lab itself

If you find a way the lab's isolation can be broken (e.g., a path by which
the app container could reach the real EC2 host, or a way the application
could be made to attack an arbitrary external host), treat that as a bug in
the lab's safety design, not a "bonus" exercise — fix it before using the
lab with students.
