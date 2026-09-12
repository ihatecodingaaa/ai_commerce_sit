# shop-lab

A small, self-contained, **intentionally vulnerable** e-commerce/support
application used to teach a realistic AI-agent attack chain:

```
customer account -> reconnaissance -> AI agent/tool discovery ->
indirect prompt injection through RAG -> sensitive information disclosure ->
limited service credential disclosure -> internal API access ->
vulnerable file upload -> application-user code execution ->
local enumeration -> privilege escalation -> root
```

Every vulnerability is a real flaw in the actual application architecture
(not a scripted "click to advance" CTF page).

> **`docs/` and `SECURITY.md` are instructor-only material** — full
> stage-by-stage mechanism writeups, architecture diagrams, and exact
> reproduction commands. If students are meant to discover the chain
> black-box (given only a URL, nothing else), these files — and this
> repo's own git history — must never reach a student-reachable host or a
> public copy of this repository. Deploy with `scripts/build_release.sh`,
> which strips exactly this material via `.gitattributes`/`.dockerignore`;
> never `git clone` this repo directly onto a target box. See
> [docs/attack-timeline.md](docs/attack-timeline.md) and
> [SECURITY.md](SECURITY.md) (instructor reading) for the full writeup and
> isolation requirements.

## Requirements

- A Linux host for the full attack chain (targets a small EC2 instance: 2
  vCPU / 4 GiB RAM, no GPU). Stages 1-7 (everything up through internal API
  access) also work fine on macOS/Windows for development.
- Docker + Docker Compose (recommended, required for Stages 8-12).
- Python 3.11+ if running natively.
- [Ollama](https://ollama.com) — CPU-only is fine.

## Quick start (Docker — recommended)

This clones the full instructor repo for local development. **For a
student-facing target host, use `scripts/build_release.sh` instead of
`git clone`** (see "Deploying to a student-facing host" below) — cloning
this repo directly there ships the instructor docs and git history (see
the warning above).

```bash
git clone <this repo> shop-lab && cd shop-lab
cp .env.example .env

# Ollama: install natively on the host (recommended for a 4 GiB box)
scripts/install_ollama.sh

docker compose build
docker compose up -d

scripts/health_check.sh   # or: curl http://localhost:5000/health
```

Visit `http://localhost:5000`, register a customer account, and start
working through the stages. See
[docs/instructor-guide.md](docs/instructor-guide.md) for exact
verification commands per stage.

To also run Ollama in a container instead of natively:

```bash
docker compose --profile with-ollama up -d
# then set OLLAMA_URL=http://ollama:11434 in .env and:
docker compose restart app
docker compose --profile with-ollama exec ollama ollama pull qwen2.5:3b
```

## Quick start (native, no Docker)

Covers **Stages 1-7 only**. The privilege-escalation chain (Stages 8-12)
is deliberately provisioned only inside the Docker app container, so a
compromise never touches your real machine/host — see
[SECURITY.md](SECURITY.md) and `scripts/setup.sh` for why.

```bash
git clone <this repo> shop-lab && cd shop-lab
scripts/setup.sh          # venv, deps, .env, seeded database
scripts/install_ollama.sh # or point OLLAMA_URL at an existing instance
python run.py
```

Visit `http://127.0.0.1:5000`.

## Manual setup (step by step)

If you prefer to run each step yourself, or are setting this up on a fresh
Amazon Linux 2023 / Ubuntu 22.04 EC2 instance:

```bash
# OS packages (Ubuntu example)
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git curl

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# edit .env if you want a non-default OLLAMA_URL/OLLAMA_MODEL/PORT

# Ollama (CPU-only is fine on a 2 vCPU / 4 GiB instance)
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                # or: sudo systemctl enable --now ollama
ollama pull qwen2.5:3b

# Database
python database/seed.py

# Run
python run.py
```

## Deploying to a student-facing host

Never `git clone` this repo onto a box students can reach — it carries
`docs/`, `SECURITY.md`, and git history that narrate every vulnerability.
Instead, build a stripped artifact and ship that:

```bash
scripts/build_release.sh ./release   # from a clean checkout of this repo
rsync -a ./release/ target-host:~/shop-lab/
ssh target-host 'cd ~/shop-lab && cp .env.example .env && docker compose build && docker compose up -d'
```

`build_release.sh` uses `git archive` (no `.git`, no history, no commit
messages) plus `.gitattributes` export-ignore rules to drop `docs/`,
`SECURITY.md`, and both `vulnerable/*/README.md` files, and swaps in
`README.release.md` as the deploy-facing `README.md`. It also verifies none
of those paths made it into the output before declaring success. Redeploy
by re-running the script and re-syncing rather than patching a target
checkout in place — that way the release process is always what's tested,
not a hand-edited copy.

## Port configuration

- App: `FLASK_PORT` in `.env` (default `5000`).
- Ollama: fixed at `11434` (Ollama's default); point `OLLAMA_URL` at it.

## Resetting the lab

```bash
scripts/reset_lab.sh
```

Recreates the database (users, products, orders, tickets, knowledge base,
fake credential, flags), clears uploaded files and logs. In Docker, run it
as root to also restore the privilege-escalation misconfiguration:

```bash
docker compose exec app scripts/reset_lab.sh               # app data only
docker compose exec --user root app scripts/reset_lab.sh   # + privesc state
```

For a hard reset between student cohorts, rebuild the container instead of
only resetting (see SECURITY.md):

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Running the tests

```bash
pip install -r requirements.txt   # includes pytest
pytest tests/ -v
```

26 of 28 tests run anywhere (no Docker/Ollama required — the chatbot tests
mock the Ollama call and the RAG/upload vulnerability tests exercise the
real application code directly). 2 tests that assert live file permissions
inside the provisioned container are skipped outside it; run those via:

```bash
docker compose exec app pytest tests/test_privilege_escalation.py -v
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `/health` shows `"ollama": "down"` | Ollama isn't running or `OLLAMA_URL` is wrong. Run `curl $OLLAMA_URL/api/tags`. The app still works for browsing/orders/tickets; only the chatbot degrades gracefully. |
| Chatbot replies are slow | Expected on CPU-only inference with 2 vCPUs — qwen2.5:3b typically takes several seconds per turn. This is normal for the target EC2 size. |
| `ollama pull qwen2.5:3b` fails / times out | Check disk space (~2 GB) and network access to ollama.com's model registry. |
| `sqlite3.OperationalError: database is locked` | Only one process should hold a long write transaction at a time; this is a lab-scale SQLite app, not built for concurrent heavy write load. |
| Docker build fails installing `sudo`/`procps` | Check outbound network access from the build host to your OS package mirror. |
| Privilege-escalation steps don't work outside Docker | Expected — see SECURITY.md and docs/instructor-guide.md. That chain is Docker-only by design. |

## Project structure

```
shop-lab/
├── README.md                  this file
├── SECURITY.md                isolation / safety requirements — read first
├── .env.example
├── requirements.txt
├── run.py                     dev entrypoint
├── Dockerfile.app             the entire "vulnerable host" container
├── docker-compose.yml
├── app/
│   ├── config.py, auth.py, logging_setup.py
│   ├── routes/                pages, auth, products, orders, support,
│   │                          chat, images (vulnerable internal API), health
│   ├── models/db.py           SQLite access
│   ├── chatbot/                Ollama client + tool-calling agent loop
│   ├── tools/                  order_lookup, customer_lookup, ticket_search,
│   │                          knowledge_base_search (vulnerable), refund_request
│   ├── rag/retrieval.py       keyword-relevance retrieval + KB indexing
│   ├── templates/, static/
├── database/
│   ├── schema.sql, seed.py
├── vulnerable/
│   ├── upload/                 image_processor.py (the RCE) + instructor README
│   └── privilege_escalation/   backup.sh + setup_privesc.sh + instructor README
├── scripts/
│   ├── setup.sh, reset_lab.sh, health_check.sh, install_ollama.sh
├── tests/
└── docs/
    ├── architecture.md, attack-timeline.md, instructor-guide.md,
    │   defensive-controls.md
```

## Known limitations / assumptions

- SQLite, not Postgres — appropriate for a single-instance lab; not
  intended for concurrent multi-cohort load on one running instance.
- The chatbot's conversation state is in-memory per process
  (`app/chatbot/agent.py`), not persisted — restarting the app clears
  active chat history (the database itself is unaffected).
- The catalog-sync-service token rotation job
  (`app/services/rotation.py`) is a single background thread per process
  (`TOKEN_ROTATION_INTERVAL_SECONDS` in `.env`, default 30 min) — this
  lab runs on Flask's single-process dev server by design, so that's
  sufficient; it would need to move to an external scheduler (cron,
  systemd timer) before running under multiple worker processes.
- Retrieval is keyword/term-overlap based, not embeddings-based — a
  deliberate choice for the target hardware (see
  docs/architecture.md#why-keyword-retrieval-instead-of-embeddings); the
  security property being taught is identical either way.
- The two tests that assert live Linux file permissions
  (`tests/test_privilege_escalation.py`) only run inside a provisioned
  container/Linux host, by necessity.
- Stages 9-12 (post-code-execution) are outside the application's own
  logging by design (see docs/defensive-controls.md, "Logging and
  detection integration") — a real deployment needs host-level detection
  for that range, which this app-only lab does not attempt to simulate.
- This was developed and exercised via `pytest` and the Flask dev server on
  a non-Linux development machine; the Docker/Linux-specific portions
  (Stages 8-12) are implemented per the documented, deterministic design
  but should be verified end-to-end on the target EC2/Linux environment
  before classroom use, per the instructor-guide verification checklist.
