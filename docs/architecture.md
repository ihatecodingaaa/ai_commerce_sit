# Architecture

## Components

```
                         +--------------------------------------------+
                         |            student's browser               |
                         +---------------------+----------------------+
                                               | HTTP (session cookie)
                                               v
+---------------------------------------------------------------------------------+
|  APP CONTAINER  (Docker: shop-lab-app)             == the "vulnerable host" ==  |
|                                                        for Stages 8-12          |
|  Flask app running as OS user `appuser`                                        |
|                                                                                  |
|  routes/  ---->  auth.py (session, require_login)                              |
|             |                                                                   |
|             +--> pages.py, api_cart.py, api_support.py, api_products.py       |
|             |       (every handler scopes queries to session user_id)          |
|             |                                                                   |
|             +--> api_chat.py --> chatbot/agent.py --> chatbot/ollama_client.py  |
|             |          |              |  (HTTP only, no DB access)             |
|             |          |              v                                        |
|             |          |      tools/*.py  (order_lookup, customer_lookup,      |
|             |          |                   ticket_search, refund_request:      |
|             |          |                   ALWAYS scoped server-side to the    |
|             |          |                   session user; knowledge_base_search:|
|             |          |                   NOT scoped -- the bug)              |
|             |          v                                                       |
|             |      rag/retrieval.py  (keyword search over kb_articles,         |
|             |                         mixes 'public' and 'internal' rows)      |
|             |                                                                   |
|             +--> api_images.py  (internal image API, X-Service-Token auth --  |
|             |    never disclosed; only image_client.py ever calls this)       |
|             |            |                                                     |
|             |            v                                                     |
|             |     vulnerable/upload/image_processor.py                        |
|             |        (imports+executes .py files dropped in the upload dir)    |
|             |            ^                                                     |
|             |            |                                                     |
|             +--> admin.py / api_admin.py (require_admin, session auth)         |
|             |            |                                                     |
|             |            v                                                     |
|             |     services/product_photos.py  (sniffs real magic bytes,       |
|             |        server picks the extension, random filename -- secure)   |
|             |                                                                  |
|             +--> api_catalog.py  (X-Catalog-Sync-Token auth -- DISCOVERABLE   |
|                  via Stage 5/6) --> services/catalog_photos.py (weak ".jpg"   |
|                  substring check) --> image_client.py --> api_images.py above |
|                  -- see "Two ways a product photo reaches the storefront"     |
|                                                                                  |
|  models/db.py --> SQLite file at /opt/shop/database/shop_lab.db                |
|                                                                                  |
|  -----------------------------------------------------------------------       |
|  Local host (inside this container only):                                      |
|    appuser (member of group `shopops`)                                         |
|    /opt/shop/scripts/backup.sh   root:shopops, mode 774 (bug)                  |
|    /etc/sudoers.d/shop-backup    appuser NOPASSWD sudo on that ONE script       |
|    /root/final_flag              root-only                                     |
+---------------------------------------------------------------------------------+
                                               |
                                               | HTTP (OLLAMA_URL), no DB/tool access
                                               v
                         +-------------------------------------------+
                         |  Ollama (host-native recommended, or the    |
                         |  optional `ollama` compose service)         |
                         |  model: qwen2.5:3b, CPU-only                |
                         +-------------------------------------------+
```

## Trust boundaries

1. **Browser <-> app**: ordinary cookie-session auth. Every customer-data
   endpoint calls `require_login` and filters by the session's `user_id`.
2. **App <-> Ollama**: plain HTTP, one direction of "real" data (tool
   results) flowing into the model's context, and one direction of
   "instructions" (system prompt + tool schemas) flowing out. The model
   never receives credentials, and never talks to the database directly.
3. **Agent <-> tools**: `app/chatbot/agent.py` decides *whose* data a
   scoped tool call is allowed to touch (the session user), independent of
   anything the model asks for. This boundary is intact for
   `order_lookup`, `customer_lookup`, `ticket_search`, `refund_request`.
   It does **not** exist for `knowledge_base_search` — that is the lab's
   deliberate vulnerability (see docs/attack-timeline.md Stage 4/5).
4. **Customer-facing API <-> internal APIs**: two completely separate
   trust boundaries, neither a customer session (`app/routes/api_images.py`'s
   `X-Service-Token` and `app/routes/api_catalog.py`'s
   `X-Catalog-Sync-Token`). Getting a customer session grants access to
   neither; only the catalog-sync token is ever discoverable at all (see
   below), and even that only reaches `/api/catalog/products`, never
   `/api/images/*` directly.
5. **App container <-> EC2 host**: the app container is the entire
   "vulnerable host" for Stages 8-12. It is a standard Docker container with
   no bind mount into the host filesystem, no `docker.sock`, no
   `--privileged`, and no added capabilities. Root obtained *inside* the
   container via the privilege-escalation chain stays inside the container.
   See SECURITY.md for the isolation requirements this depends on.
6. **Admin product photos <-> catalog-sync product photos**: two
   independent code paths to the same `products.image_path` column, with
   very different validation postures. See below.

## Two ways a product photo reaches the storefront, not one

It's an easy assumption that a product's photo always goes through the
same, hardened path. It doesn't -- that's the point. Both end up in the
same `products.image_path` column and render identically on
`/products`/`/products/<id>`, but they get there completely differently:

| | `POST/PUT /api/admin/products` (photo field) | `POST /api/catalog/products` (photo field) |
|---|---|---|
| Who can call it | logged-in `role='admin'` users only (`app/auth.py::require_admin`) | anyone with the current `catalog-sync-service` token (discovered via Stage 5/6, not a customer login, not an admin session) |
| What it's *for* | a human admin managing the catalog by hand | the warehouse/inventory system pushing new products with no human present |
| File type check | real file content, sniffed by magic bytes -- `app/services/product_photos.py` | whether `.jpg` appears anywhere in the filename -- `app/services/catalog_photos.py` |
| Stored filename | server-generated `uuid4().hex` + the extension the sniffer determined, never the client's filename | forwarded byte-for-byte, real filename (and extension) intact, to the internal image API below |
| What happens to the file | served back as raw bytes via `send_from_directory`, never interpreted as anything but image bytes | passed through `app/services/image_client.py` to `POST /api/images/upload` (support-image-service's own, never-disclosed credential -- see `app/services/rotation.py`), where `vulnerable/upload/image_processor.py` may **import and execute** `.py`-named files, before a copy is also saved under `PRODUCT_PHOTO_DIR` so the product still displays normally |

`/api/images/upload` itself is not directly reachable by an outside
attacker in this version of the lab -- see `vulnerable/upload/README.md`
for the deliberate vulnerability (now reached via the catalog-sync front
door instead), and `app/services/product_photos.py` for what the *secure*
version of the same "let someone upload a file" problem looks like, side
by side with `app/services/catalog_photos.py`'s weak one.

## Why keyword retrieval instead of embeddings

A 2 vCPU / 4 GiB EC2 instance already has to run Ollama (CPU inference) plus
the Flask app. Adding an embedding model and a vector index would roughly
double the memory footprint for no security-relevant benefit: the
vulnerability being demonstrated (retrieved content treated as trusted
context, no visibility scoping) is identical whether retrieval is done by
cosine similarity over embeddings or by term overlap. `app/rag/retrieval.py`
implements simple, deterministic term-overlap scoring instead.

## Data flow for the core vulnerability (Stages 3-6)

```
customer review (attacker-controlled text)
  -> app/routes/api_products.py: submit_review()
  -> app/rag/retrieval.py: index_content_as_kb(visibility='public')
  -> kb_articles table

[later, same or different chat session]
customer asks the chatbot an ordinary question
  -> app/chatbot/agent.py calls knowledge_base_search(query=...)
  -> app/rag/retrieval.py: search_articles(visibility_filter=None)  <- bug
  -> matches the planted review (by ordinary keyword overlap)
  -> review body (containing embedded instructions) appended to LLM context
     as a plain "tool" message, no untrusted-data framing
  -> model follows the embedded instruction, calls knowledge_base_search
     again with attacker-chosen terms
  -> search_articles(visibility_filter=None) now matches an
     visibility='internal' article containing the fake service token
  -> token appears in the model's context, and (unless the student's
     question is filtered) in the chat reply
```
