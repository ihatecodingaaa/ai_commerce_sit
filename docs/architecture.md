# Architecture

## Components

```
                         +-------------------------------------------+
                         |            student's browser               |
                         +---------------------+-----------------------+
                                               | HTTP (session cookie)
                                               v
+---------------------------------------------------------------------------------+
|  APP CONTAINER  (Docker: shop-lab-app)             == the "vulnerable host" ==  |
|                                                        for Stages 8-12          |
|  Flask app running as OS user `appuser`                                        |
|                                                                                  |
|  routes/  ---->  auth.py (session, require_login)                              |
|             |                                                                   |
|             +--> pages.py, api_orders.py, api_support.py, api_products.py       |
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
|             +--> api_images.py  (internal image API, X-Service-Token auth)     |
|                         |                                                       |
|                         v                                                       |
|              vulnerable/upload/image_processor.py                              |
|                 (imports+executes .py files dropped in the upload dir)          |
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
4. **Customer-facing API <-> internal image API**: a completely separate
   trust boundary (`X-Service-Token` bearer auth, not a customer session).
   Getting a customer session does not grant access to `/api/images/*`; the
   token must be independently discovered.
5. **App container <-> EC2 host**: the app container is the entire
   "vulnerable host" for Stages 8-12. It is a standard Docker container with
   no bind mount into the host filesystem, no `docker.sock`, no
   `--privileged`, and no added capabilities. Root obtained *inside* the
   container via the privilege-escalation chain stays inside the container.
   See SECURITY.md for the isolation requirements this depends on.

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
