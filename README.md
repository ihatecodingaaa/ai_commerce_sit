# AI Commerce Security Lab

A self-contained, intentionally vulnerable AI-security CTF for **authorized education only**. The lab uses synthetic users, synthetic credentials, isolated Docker networking, and localhost-only exposed ports.

## Scope and safety

- Run only on a machine you control.
- Do not add production credentials, AWS credentials, reused passwords, or real customer data.
- Do not expose ports 8080/8081 publicly.
- The final `root` state is root **inside the disposable image-service container**, never host root.
- No component is given the Docker socket, host filesystem, privileged-container mode, or arbitrary external-target functionality.

## Start

```bash
cp .env.example .env
docker compose up --build
```

Storefront: `http://127.0.0.1:8080`

The image-management API is bound to `http://127.0.0.1:8081` for local Burp Suite exercises, but requires its scoped service credential.

## Reset

```bash
docker compose down -v
docker compose up --build
```

## LLM modes

Default deterministic mode requires no API key:

```env
LLM_PROVIDER=mock
```

Optional local OpenAI-compatible mode:

```env
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_MODEL=qwen2.5:3b
```

The model has no shell, `exec`, or command-running tool. Backend services remain responsible for authorization.

## Customer access

Create any customer account at `/register`. Seeded synthetic accounts also exist for application realism:

- `alice@example.test`
- `bob@example.test`
- `charlie@example.test`

Seed password: `Customer123!`

These are ordinary customer identities, not privileged accounts.

## Student objective

Start as a normal customer. Reconnoitre the application and chatbot, observe requests in Burp Suite, and collect stage flags. Do not assume the AI itself has OS command execution.

Flag format:

```text
FLAG{...}
```

The complete solution is intentionally excluded from this student-facing README. Instructors should use `docs/instructor-guide.md`.

## Automated validation

```bash
python tests/validate.py
```

The GitHub Actions workflow also performs a clean Docker build/start, runs the complete deterministic validation, prints logs on failure, and tears the lab down.
