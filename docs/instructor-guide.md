# Instructor Guide

This document contains the intended solution path for the isolated AI Commerce Security Lab. Do not expose it to students during an assessment.

## Architecture and trust boundaries

```text
CUSTOMER INPUT          -> UNTRUSTED
RAG DOCUMENT            -> UNTRUSTED
LLM OUTPUT              -> UNTRUSTED
TOOL REQUEST            -> MUST BE AUTHORIZED BY BACKEND
SERVICE TOKEN           -> LIMITED PRIVILEGE
APPLICATION USER        -> LOW PRIVILEGE
ROOT                    -> FINAL CONTAINER PRIVILEGE BOUNDARY
```

The vulnerable build intentionally violates document- and tool-level authorization. The model itself has no arbitrary shell tool.

## Intended progression

1. Register/login as an ordinary customer and browse the application.
2. Use `/about`, product pages, support, and normal HTTP traffic to discover that support handles image-management issues and that Alice Tan is Head of Customer Operations.
3. Discover that customer reviews are searchable by the support RAG layer.
4. Submit a review containing instructions aimed at the support agent. The deterministic mock mode is influenced when retrieved attacker content contains an imperative, targets internal image/support configuration, and addresses the support agent/assistant/system-instruction concept. It is intentionally not tied to one exact exploit sentence.
5. Ask the chatbot about internal image/support configuration. `vulnerable_document_filter()` fails to enforce document-level authorization and `vulnerable_tool_authorization()` allows the internal support-configuration tool for a customer-selected path.
6. The resulting disclosure includes the synthetic `support-image-service` credential. This token is limited to image metadata/upload and is not an admin, database, host, or root credential.
7. In Burp Repeater, send the credential as `Authorization: Bearer <token>` to `http://127.0.0.1:8081/api/images` and `/api/images/upload`.
8. The upload endpoint validates only the final image extension while the downstream processor treats a compound filename containing `.py.` as a Python processing job. A file such as `diagnostic.py.jpg` therefore executes as the low-privilege `appuser` inside the image-service container.
9. Local enumeration should reveal `/usr/local/bin/backup-helper` is setuid root. Its implementation calls `tar` by name instead of an absolute path, so a controlled `PATH` can substitute a different executable.
10. Exploiting that helper reaches root only inside the image-service container, where `/root/root.flag` contains the final flag.

## Flags

- `FLAG{internal_information_disclosed}`
- `FLAG{service_token_obtained}`
- `FLAG{application_user}`
- `FLAG{root_compromise}`

The validator asserts the major state transitions rather than exposing every flag in the UI.

## Possession boundaries

An ordinary customer has only their account/session. The disclosed service token authenticates only to the image service. It does not make the user an application administrator and it cannot directly provide OS access. Server-side execution is obtained only through the intentionally vulnerable upload processor. Root is obtained only after local enumeration and exploitation of the intentionally unsafe setuid helper.

## Logging

Server logs emit synthetic request IDs and events such as `customer_registered`, `chatbot_request`, `tool_invoked`, `document_retrieved`, `internal_document_retrieved`, `service_token_accessed`, `image_upload`, and `code_execution`. The service token is redacted when logged.

## Burp Suite workflow

Configure the browser to proxy through Burp. Register/login at port 8080, inspect normal chatbot requests, then replay image-service requests to localhost port 8081 after obtaining the scoped credential. The APIs use ordinary HTTP forms/JSON and a Bearer header, so Repeater is sufficient.

## Validation

From a clean checkout:

```bash
docker compose down -v
docker compose up -d --build
python tests/validate.py
```

The validation script creates a fresh customer, verifies customer-to-admin access fails, injects attacker-controlled RAG content, obtains the synthetic token through the vulnerable AI path, verifies image-service authorization, demonstrates execution as `appuser`, and exercises the container-local privilege-escalation path to the root flag.

## Defensive teaching version

The source includes a `secure_tool_authorization()` counterpart. A hardened exercise should additionally replace the vulnerable document filter with per-document ACL enforcement, refuse instructions from retrieved text, redact service credentials from model-visible context, validate uploads by decoded file type/content, store uploads outside executable contexts, remove compound-name execution behavior, and remove the setuid helper/PATH misuse.
