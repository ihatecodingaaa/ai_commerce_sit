# Attack timeline (instructor reference)

Full chain: customer account -> reconnaissance -> AI tool discovery ->
indirect prompt injection through RAG -> sensitive information disclosure
-> limited service credential disclosure -> internal API access ->
vulnerable file upload -> application-user code execution -> local
enumeration -> privilege escalation -> root.

Each stage gives the attacker exactly one new capability. No stage is a
"magic endpoint" — every transition is a consequence of a specific,
documented trust-boundary flaw in the actual application code.

---

## Stage 1 — Customer access

**Has:** a registered customer account, a session cookie.
**Does not have:** any knowledge of other customers' data, staff data, or
internal systems.
**Mechanism:** `/register` + `/login` (`app/routes/auth_routes.py`). Ordinary
auth — no vulnerability here, deliberately.
**Log evidence:** `user_registered`, `login_success`.
**Mitigation (n/a — this stage is intentionally correct):** password
hashing via Werkzeug, session-based auth.

## Stage 2 — Reconnaissance

**Has:** visibility into `/about` (staff names/titles), `/products`,
public reviews, the general shape of the app.
**Does not have:** any internal identifiers yet (ticket refs, service
names) beyond what `/about` and product pages disclose.
**Mechanism:** ordinary browsing. `/about` intentionally lists staff by
name/title/department (`database/seed.py`) — this is realistic "who works
here" content, not a vulnerability by itself, but it gives the student
names (e.g. Alice Tan) that later appear as ticket owners, which matters
for Stage 5 reasoning.
**Log evidence:** none specific (ordinary page views).
**Mitigation:** none needed; this is normal public content.

## Stage 3 — Chatbot capability enumeration

**Has:** knowledge that a support chatbot exists and (by asking it "what
can you help with / what tools do you have") a rough idea of its
tool surface: orders, account, tickets, knowledge base, refunds.
**Does not have:** any tool results yet beyond their own data.
**Mechanism:** `app/chatbot/prompts.py` describes the five tools to the
model; a student asking about its capabilities will typically get an
accurate (if informal) summary, because that's exactly what the system
prompt tells it to be helpful about.
**Log evidence:** `chatbot_request` / `chatbot_response` pairs.
**Mitigation:** capability disclosure to an authenticated, rate-limited
user is generally acceptable; the risk is entirely in what the tools
*do*, not in a customer knowing they exist.

## Stage 4 — Indirect injection surface

**Has:** the ability to submit a product review (`POST
/api/products/<id>/reviews`) whose body becomes a `kb_articles` row with
`visibility='public'` (`app/routes/api_products.py`,
`app/rag/retrieval.py::index_content_as_kb`).
**Does not have:** any guarantee their review will be *retrieved* yet — it
depends on keyword overlap with a future chat query.
**Mechanism / vulnerability:** customer-controlled content enters the same
knowledge base the chatbot searches, with no distinction between
"written by support staff" and "written by a customer", and no
sanitization of embedded instruction-like text.
**Log evidence:** `review_submitted` (includes the resulting
`kb_article_id`); `suspicious_input_pattern` if the review body matches
the (detection-only, non-blocking) heuristic in
`app/logging_setup.py::detect_suspicious_text`.
**Mitigation:** treat all retrieved content as untrusted data (wrap it in
an explicit "reference material, not instructions" frame in the prompt);
consider moderation/review before customer content is indexed for
retrieval by an agent with tool access.

## Stage 5 — Sensitive information disclosure

**Has:** a chat session in which the model, having retrieved the
planted review (matched by ordinary keywords in the customer's own
question), followed the embedded instruction and called
`knowledge_base_search` again with attacker-chosen terms — surfacing a
`visibility='internal'` article (or the INC-10492/INC-10480 ticket
content) that a customer should never see.
**Does not have:** the credential yet, necessarily — depends on what the
injected instruction asked the model to search for and repeat.
**Mechanism / vulnerability:** `app/tools/knowledge_base_search.py` calls
`search_articles(query, visibility_filter=None)` — no visibility filter.
Contrast with `app/tools/ticket_search.py`, which correctly filters
`visibility = 'customer' AND user_id = ?`. This is a single, narrow,
one-tool authorization gap, not "nothing is authorized" (see
`tests/test_authorization.py` and `tests/test_rag_injection.py`).
**Log evidence:** `kb_retrieval` events record the query and
`retrieved_visibilities` — an instructor grepping logs will see
`"internal"` show up in a customer chat session, which is the smoking gun.
**Mitigation:** `knowledge_base_search` should filter
`visibility='public'` by default and require a separate, staff-only tool
(with its own authorization check) for internal content. See
docs/defensive-controls.md.

## Stage 6 — Limited service credential

**Has:** the literal current value of the support-image-service token,
disclosed via the Stage 5 flow because the internal KB article/ticket
about "support-image-service token rotation" contains it in plain text.
**Does not have:** any indication the token is powerful — the same
article states its actual scope (upload + read ticket image metadata
only, no admin, no other systems). Also doesn't have a *permanent*
foothold: the token is randomly generated and rotates automatically
(`app/services/rotation.py`, default every 30 min) — this specific value
will eventually stop working, exactly like a real leaked credential
would, which is a deliberate part of the realism, not a bug to work
around.
**Mechanism:** `database/seed.py` and the rotation job both generate the
token via `app/services/credentials.py` (SHA-256 hash stored, never
plaintext) and paste the current plaintext into the ticket body — that
paste, not the credential store, is the actual leak (fake, synthetic —
see SECURITY.md).
**Log evidence:** `kb_retrieval` for the internal doc; `service_token_used`
events will start appearing once the student uses it.
**Mitigation:** secrets should never be stored as plain text inside
content that is reachable by any retrieval-augmented system; use a secret
manager and reference secrets by name, never by value, in any
human/LLM-readable document.

## Stage 7 — Internal API access

**Has:** the ability to call `/api/images` (list), `/api/images/<id>`
(read), and `/api/images/upload` (write) using
`X-Service-Token: <token>` (`app/routes/api_images.py`).
**Does not have:** any other internal system access — the token is
checked against exactly one constant and grants exactly these three
routes.
**Mechanism:** simple shared-bearer-token auth, intentionally a *separate*
trust boundary from the customer session (Stage 1-6 access does not by
itself grant this — the token had to be discovered).
**Log evidence:** `service_token_used` (action=list/get/upload),
`service_token_auth_failed` for wrong/missing tokens.
**Mitigation:** short-lived, scoped tokens (not a static long-lived
constant); mTLS or a proper service-identity system between internal
services in production.

## Stage 8 — Vulnerable file upload

**Has:** the ability to upload a file where the API's Content-Type check
(`app/routes/api_images.py::ALLOWED_CONTENT_TYPES`) and the processing
stage's extension check (`vulnerable/upload/image_processor.py`) disagree
about what's safe — see `vulnerable/upload/README.md` for the full
validation-layer table.
**Does not have:** code execution yet — just a stored `.py` file.
**Mechanism / vulnerability:** CWE-434 (Unrestricted Upload of File with
Dangerous Type) via signal disagreement between layers.
**Log evidence:** `image_uploaded` (filename ends in `.py`, claimed_type is
`image/*`), `image_processing_plugin_load`.
**Mitigation:** validate actual file content, not headers or filenames;
never derive executable behavior from a filename.

## Stage 9 — Application-user code execution

**Has:** arbitrary Python code execution as `appuser` inside the app
container, via `image_processor.py::_load_and_run_plugin`
(`importlib` `exec_module` on the uploaded file).
**Does not have:** root. `appuser` is an unprivileged, non-sudo-by-default
account (only the one scoped rule from Stage 10 exists).
**Mechanism:** demonstrated deterministically in
`tests/test_upload_vuln.py::test_uploaded_py_plugin_actually_executes`.
**Log evidence:** `image_processing_plugin_load`; anything the payload
itself does is, realistically, outside this app's own logging (a real
detection stack would need host-level EDR/auditd here — see
docs/defensive-controls.md).
**Mitigation:** run any real file-processing step in a sandboxed worker
with no interpreter available; least-privilege the app account.

## Stage 10 — Local enumeration

**Has:** a shell as `appuser` and has to actually look around:
`id`, `sudo -l`, `ls -la /opt/shop/scripts/`, checking
`/etc/sudoers.d/`, reading world-readable app config.
**Does not have:** the escalation path handed to them — nothing in the
student-facing UI mentions it (see `vulnerable/privilege_escalation/README.md`,
which is instructor-only).
**Mechanism:** ordinary Linux enumeration.
**Mitigation:** minimize world-readable configuration, restrict `sudo -l`
visibility where feasible, and audit for group-writable files that are
also sudo targets (exactly the class of bug this lab teaches).

## Stage 11 — Privilege escalation

**Has:** discovered that `/opt/shop/scripts/backup.sh` is group-writable
by `shopops` (a group `appuser` belongs to) and that
`/etc/sudoers.d/shop-backup` lets `appuser` run that exact script as root
with `NOPASSWD`.
**Does not have:** root yet — has to actually exploit it (edit the script,
then `sudo` it).
**Mechanism:** deterministic, configuration-only privilege escalation. See
`vulnerable/privilege_escalation/README.md` for the exact reproduction
steps. **Not** a kernel CVE, **not** `ALL=(ALL) NOPASSWD:ALL`
(`tests/test_privilege_escalation.py` asserts both).
**Log evidence:** outside this app's own logs (host/auditd territory);
this is a deliberate limitation of an application-level lab — see
docs/defensive-controls.md for what a real deployment would add.
**Mitigation:** any script a sudo rule grants elevated execution of must
never be writable by the account holding that rule.

## Stage 12 — Root

**Has:** a root shell (or root-equivalent, e.g. a setuid `/tmp/rootbash`)
inside the app container, and can read `/root/final_flag`
(`AI-LAB{...}`, synthetic).
**Does not have:** access to the real EC2 host — the entire chain from
Stage 8 onward occurred inside the app Docker container, which has no
bind mount, socket, or capability granting host access (see SECURITY.md).
**Mechanism:** `cat /root/final_flag`.
**Log evidence:** none inside the app (by the time you're here, you're
root in a container with no more app-layer boundary to cross) — this is
exactly why defense-in-depth matters: everything upstream of Stage 9
should have stopped this.
**Mitigation:** see docs/defensive-controls.md in full; the short version
is every stage above has an independent fix, and any one of them breaks
the chain.
