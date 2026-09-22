# Attack timeline (instructor reference)

Full chain: customer account -> reconnaissance -> AI tool discovery ->
indirect prompt injection through RAG -> sensitive information disclosure
-> **(branch)** misplaced admin credential & account takeover -> admin-
session code execution **[Path B, shortcut]**, **or** limited service
credential disclosure -> internal API access -> vulnerable file upload
**[Path A]** -> application-user code execution (both paths converge here)
-> local enumeration -> privilege escalation, hop 1 (appuser -> opsuser,
misplaced credential) -> privilege escalation, hop 2 (opsuser -> root, tar
wildcard injection) -> root.

Each stage gives the attacker exactly one new capability. No stage is a
"magic endpoint" — every transition is a consequence of a specific,
documented trust-boundary flaw in the actual application code.

Two independent routes reach application-user code execution (Stage 11):
**Path A** (Stages 8-10) abuses the catalog-sync-service *machine* token;
**Path B** (Stages 6-7) abuses a misplaced *human* admin credential instead
and gets there in two stages instead of five. Both are intentional, valid,
and left fully working — an instructor can teach either, or both, without
one interfering with the other. Everything from Stage 11 onward (local
enumeration through root) is shared by both paths.

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

**Has:** visibility into `/about` (two staff names, named in passing in
the page copy, not a directory), `/products`, public reviews, the
general shape of the app.
**Does not have:** any internal identifiers yet (ticket refs, service
names) beyond what `/about` and product pages disclose.
**Mechanism:** ordinary browsing. `/about`'s copy (`app/templates/about.html`)
mentions two real staff members by name — Priya Nair and Dana Okafor,
pulled from `database/seed.py`'s `employees` table via `app/routes/pages.py`'s
`about()` route — as part of an ordinary "who makes this" paragraph, not a
staff directory or bio grid. This is realistic "who works here" content, not
a vulnerability by itself, but it gives the student real names that later
appear as ticket owners (Priya Nair owns the leaked `INC-10493` token-rotation
ticket; Dana Okafor owns a customer ticket; Marcus Webb, also seeded but
never mentioned on `/about`, owns the Stage 6 admin-credential ticket —
the student has to correlate ticket ownership themselves, not just recognize
a name they've already seen), which matters for Stage 5 reasoning.
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
`visibility='internal'` article that a customer should never see. Which
article depends entirely on what the injected instruction asked the model
to search for and repeat: it might be the INC-10493/INC-10480 service-token
content (Stage 8), or it might be the INC-10485 admin-credential content
(Stage 6) — same mechanism, different targets.
**Does not have:** any specific credential yet — this stage is the
disclosure *mechanism*, not any one secret.
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

## Stage 6 — Misplaced admin credential & account takeover (Path B begins)

**Has:** the current plaintext password for the `admin` account (a
*human*, role-based account — not a service token), disclosed via the
Stage 5 mechanism targeting the `INC-10485` ticket
(`database/seed.py`'s "site admin password reset after Q3 access review").
**Does not have:** anything Stage 5 didn't already grant, until they
actually use it — the disclosure and the account takeover are separate
attacker actions.
**Mechanism / vulnerability:** `database/seed.py` generates a fresh random
admin password every seed run, hashes it correctly for `users.password_hash`
(that storage is fine), but *also* pastes the plaintext into an internal
ticket body — the exact same "a real secret got pasted into
LLM-retrievable content" bad practice as the catalog-sync-service token
(Stage 8), just for a login credential instead of a bearer token this
time. The attacker logs in as `admin` through the ordinary, unmodified
`/login` form (`app/auth.py` — no vulnerability in the login path itself,
same as Stage 1).
**Log evidence:** `kb_retrieval` for the `INC-10485` article;
`login_success` for the `admin` account from a session that was, moments
earlier, an ordinary customer session in the logs — an instructor
correlating `login_success(username=admin)` against the browsing customer
account is the smoking gun here.
**Mitigation:** never store a real credential's plaintext anywhere outside
the account's own (hashed) storage — not in a ticket, log, or any other
LLM- or human-readable document; require MFA on staff/admin accounts so a
leaked password alone isn't sufficient. See docs/defensive-controls.md.

## Stage 7 — Admin-session code execution via ticket screenshot (Path B, shortcut)

**Has:** arbitrary Python code execution as `appuser`, reached directly
from the Stage 6 admin session — this single stage does the job Path A
needs three stages (8-10) for.
**Does not have:** anything beyond what Stage 11 (below) already covers;
this stage's *outcome* is identical to Path A's, just reached differently.
**Mechanism / vulnerability:** `app/routes/api_admin_tickets.py::upload_ticket_screenshot`
(legitimate admin functionality — attaching a reference screenshot to a
customer ticket) forwards the uploaded file's bytes, filename, and
browser-supplied Content-Type, completely unchanged, through
`app/services/image_client.py::upload_screenshot` to the same internal
image service Path A eventually reaches. Unlike
`app/services/catalog_photos.py` (Path A), this route has **no filename
check at all** — `app/routes/api_images.py` only validates the
attacker-controlled `Content-Type` header against an allowlist
(`image/jpeg`, `image/png`, `image/gif`) and then unconditionally runs
`vulnerable/upload/image_processor.py` against the real filename. An admin
session can therefore attach a ticket "screenshot" literally named
`plugin.py` with `Content-Type: image/jpeg` and reach the exact same
`_load_and_run_plugin` code-execution sink as Stage 10 — no double-extension
trick needed, since there's no filename gate to bypass here at all.
**Log evidence:** `admin_ticket_screenshot_uploaded`, `image_uploaded`
(filename ends in `.py` despite an image Content-Type),
`image_processing_plugin_load`.
**Mitigation:** validate actual file content, not headers or filenames, on
*every* caller of the internal image service, not just the one an outside
attacker was assumed to reach; an authenticated admin session should not
be treated as an implicitly safe upload source. See
docs/defensive-controls.md.

## Stage 8 — Limited service credential (Path A begins)

**Has:** the literal current value of the catalog-sync-service token,
disclosed via the Stage 5 flow because the internal KB article/ticket
about "catalog-sync-service token rotation" contains it in plain text.
**Does not have:** any indication the token is powerful — the same
article states its actual scope (product creation only, no admin, no
other systems). Also doesn't have a *permanent* foothold: the token is
randomly generated and rotates automatically (`app/services/rotation.py`,
default every 30 min) — this specific value will eventually stop
working, exactly like a real leaked credential would, which is a
deliberate part of the realism, not a bug to work around.
**Mechanism:** `database/seed.py` and the rotation job both generate the
token via `app/services/credentials.py` (SHA-256 hash stored, never
plaintext) and paste the current plaintext into the ticket body — that
paste, not the credential store, is the actual leak (fake, synthetic —
see SECURITY.md). support-image-service has its own, *separate*
credential (used by `app/services/image_client.py`) that is never
rotated on a timer or pasted anywhere — see Stage 11.
**Log evidence:** `kb_retrieval` for the internal doc; `service_token_used`
events (service=catalog-sync-service) will start appearing once the
student uses it.
**Mitigation:** secrets should never be stored as plain text inside
content that is reachable by any retrieval-augmented system; use a secret
manager and reference secrets by name, never by value, in any
human/LLM-readable document.

## Stage 9 — Internal API access (as an automation client, not a human)

**Has:** the ability to call `POST /api/catalog/products`
(`app/routes/api_catalog.py`) using `X-Catalog-Sync-Token: <token>` — a
route a mere customer session, admin or not, cannot reach at all, since
it checks only this token and never looks at cookies.
**Does not have:** any other internal system access — the token is
checked against exactly one stored hash and grants exactly this one
route. It also does not yet have code execution — just the ability to
create a product, optionally with a photo.
**Mechanism:** simple shared-bearer-token auth, intentionally a *separate*
trust boundary from both the customer session AND the admin session
(Stage 1-8 access does not by itself grant this — the token had to be
discovered). This isn't a token invented for the exploit: a warehouse/
inventory system pushing new products with no human admin present is a
completely ordinary integration shape, the same as `api_images.py`'s
support-image-service token is for ticket-screenshot storage.
**Log evidence:** `service_token_used` (service=catalog-sync-service,
action=sync_product), `service_token_auth_failed` for wrong/missing
tokens.
**Mitigation:** short-lived, scoped tokens (not a static long-lived
constant); mTLS or a proper service-identity system between internal
services in production.

## Stage 10 — Vulnerable file upload

**Has:** the ability to upload a "product photo" where
`app/services/catalog_photos.py::looks_like_jpeg_filename` (does the
filename merely *contain* `.jpg`?) and the processing stage's extension
check (`vulnerable/upload/image_processor.py`, the *real*, final
extension) disagree about what's safe — see `vulnerable/upload/README.md`
for the full validation-layer table. A file named `plugin.jpg.py` passes
the first check and is executed anyway by the second.
**Does not have:** code execution yet in this step alone -- forwarding
into `UPLOAD_DIR` (via `app/services/image_client.py`, using the
backend's own held support-image-service credential — the attacker's
catalog-sync-service token never touches that internal call directly) is
what triggers Stage 11.
**Mechanism / vulnerability:** CWE-434 (Unrestricted Upload of File with
Dangerous Type) via signal disagreement between layers — the same
disagreement class this lab has always taught, just moved one layer
further from the attacker (`api_catalog.py`'s weak filename substring
check, not `api_images.py`'s Content-Type check, is now the one an
outside attacker actually has to satisfy).
**Log evidence:** `catalog_sync_product_created` (has_photo=true),
`image_uploaded` (filename contains `.jpg` but doesn't end with it),
`image_processing_plugin_load`.
**Mitigation:** validate actual file content, not headers or filenames;
never derive executable behavior from a filename.

## Stage 11 — Application-user code execution (Path A and Path B converge)

**Has:** arbitrary Python code execution as `appuser` inside the app
container, via `image_processor.py::_load_and_run_plugin`
(`importlib` `exec_module` on the uploaded file). Reached either via Path A
(Stage 10, catalog-sync product photo) or Path B (Stage 7, admin ticket
screenshot) — from here on, both paths are identical.
**Does not have:** root. `appuser` is an unprivileged, non-sudo account —
it has no sudo rule at all (see Stage 13).
**Mechanism:** demonstrated deterministically in
`tests/test_catalog_sync.py::test_double_extension_photo_actually_executes`
(Path A) and `tests/test_upload_vuln.py::test_uploaded_py_plugin_actually_executes`
(the underlying processing bug, in isolation, shared by both paths).
**Log evidence:** `image_processing_plugin_load`; anything the payload
itself does is, realistically, outside this app's own logging (a real
detection stack would need host-level EDR/auditd here — see
docs/defensive-controls.md).
**Mitigation:** run any real file-processing step in a sandboxed worker
with no interpreter available; least-privilege the app account.

## Stage 12 — Local enumeration

**Has:** a shell as `appuser` and has to actually look around:
`id`, `sudo -l` (shows nothing — appuser has no sudo rule at all now),
`ls -la /opt/shop/`, reading world-readable app config and logs.
**Does not have:** the escalation path handed to them — nothing in the
student-facing UI mentions it (see `vulnerable/privilege_escalation/README.md`,
which is instructor-only).
**Mechanism:** ordinary Linux enumeration.
**Mitigation:** minimize world-readable configuration and logs; never let a
provisioning/deploy log retain a plaintext secret, however "temporary".

## Stage 13 — Privilege escalation, hop 1: appuser -> opsuser (misplaced credential)

**Has:** discovered that `/opt/shop/logs/provisioning.log` is world-readable
and contains a plaintext password for a second local account, `opsuser`,
pasted there at provisioning time and never cleaned up — the same
"secret got logged somewhere it shouldn't" mistake as Stage 6, this time
at the OS layer instead of the database layer.
**Does not have:** root, or even any elevated capability yet — `opsuser`
is a normal, unprivileged shell account in its own right; what it *does*
have is set up in Stage 14.
**Mechanism:** deterministic, configuration-only credential exposure — no
group membership is involved anywhere in this hop. See
`vulnerable/privilege_escalation/README.md` for exact reproduction steps.
**Log evidence:** outside this app's own logs (host/auditd territory) —
same deliberate limitation as Stage 14/15; see docs/defensive-controls.md.
**Mitigation:** never write secrets into log files, even "temporarily";
treat any provisioning/deploy log as something that will eventually be
read by someone who shouldn't have the values in it.

## Stage 14 — Privilege escalation, hop 2: opsuser -> root (tar wildcard injection)

**Has:** discovered that `/opt/shop/scripts/backup.sh` — root-owned, NOT
writable by `opsuser` this time — is runnable as root via a scoped
`NOPASSWD` sudo rule (`/etc/sudoers.d/shop-ops`), and that the script
itself runs `tar -czf <dest> *` over a directory (`/opt/shop/backups/staging/`)
that `opsuser` owns and can write to. A crafted pair of filenames
(`--checkpoint=1`, `--checkpoint-action=exec=sh payload.sh`) gets expanded
by the shell's glob and parsed by `tar` as extra arguments instead of file
names — the classic GTFOBins `tar` wildcard-injection technique.
**Does not have:** root yet — has to actually exploit it (plant the
checkpoint files, then `sudo` the script).
**Mechanism:** deterministic, configuration-only privilege escalation. See
`vulnerable/privilege_escalation/README.md` for the exact reproduction
steps. **Not** a kernel CVE, **not** `ALL=(ALL) NOPASSWD:ALL`, **not**
group-writable-file-based (`tests/test_privilege_escalation.py` asserts
all three).
**Log evidence:** outside this app's own logs (host/auditd territory);
this is a deliberate limitation of an application-level lab — see
docs/defensive-controls.md for what a real deployment would add.
**Mitigation:** any script a sudo rule grants elevated execution of must
never pass an unquoted/glob argument straight to a program (`tar`,
`chown`, `rsync`, ...) that treats certain argument patterns specially,
even when the script file itself is properly locked down.

## Stage 15 — Root

**Has:** a root shell (or root-equivalent, e.g. a setuid `/tmp/rootbash`)
inside the app container, and can read `/root/final_flag`
(`AI-LAB{...}`, synthetic).
**Does not have:** access to the real EC2 host — the entire chain from
Stage 7/10 onward occurred inside the app Docker container, which has no
bind mount, socket, or capability granting host access (see SECURITY.md).
**Mechanism:** `cat /root/final_flag`.
**Log evidence:** none inside the app (by the time you're here, you're
root in a container with no more app-layer boundary to cross) — this is
exactly why defense-in-depth matters: everything upstream of Stage 11
should have stopped this.
**Mitigation:** see docs/defensive-controls.md in full; the short version
is every stage above has an independent fix, and any one of them breaks
the chain.
