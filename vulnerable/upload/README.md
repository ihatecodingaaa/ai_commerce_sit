# Vulnerable upload chain: instructor notes (Stage 6-9)

**Do not link this file from student-facing pages.**

## The chain, layer by layer

| Layer | File | What it checks | Attacker-controlled? |
|---|---|---|---|
| Frontend (conceptual) | n/a — this is a machine-to-machine API | n/a | n/a |
| Auth | `app/routes/api_catalog.py::_require_catalog_sync_token` | `X-Catalog-Sync-Token` header hashed and compared against the current rotated catalog-sync-service credential (`app/services/credentials.py`) | Yes, if the current value is leaked (Stage 6) |
| API | `app/services/catalog_photos.py::looks_like_jpeg_filename` | whether `.jpg` appears **anywhere** in the client-supplied filename | **Yes, fully** |
| Forwarding | `app/services/image_client.py::upload_screenshot_bytes` → `app/routes/api_images.py::upload_image` | multipart `Content-Type` of the forwarded part (still whatever the original attacker request claimed — this backend call just passes it through) | Yes (indirectly — set by the attacker's original request, not by this backend) |
| Storage | `api_images.py::_weak_sanitize_filename` | strips path separators only; keeps everything else (including shell metacharacters) verbatim | Yes |
| Processing | `vulnerable/upload/image_processor.py` | shells out to ImageMagick's `convert` with the stored file's path interpolated into the command line, unescaped | Yes |

The attacker-facing check only validates that `.jpg` is a *substring* of the
filename and that the filename *ends* in a real image extension — neither
check has anything to do with whether the filename is otherwise safe to drop
into a shell command. Processing takes that filename completely on trust.
A filename like `photo.jpg;id>proof.txt #.jpg` passes both upstream checks
(contains `.jpg`, ends in `.jpg`) while also carrying a `;`-separated shell
command that runs once `image_processor.py` builds its `convert` command
line.

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

The filename itself is the payload — no need for a `.py` file at all. The
injected command must avoid literal `/` characters: `_weak_sanitize_filename`
runs `os.path.basename()` on the client-supplied filename *before* anything
else touches it, and `os.path.basename` truncates everything up to and
including the last `/` — a `/` anywhere in the crafted filename destroys
whatever came before it. `image_processor.py` happens to run the shell
command with its working directory set to the upload directory itself (an
ordinary, plausible implementation choice — see its own docstring), so a
bare relative-path write is enough:

```python
import requests

files = {"photo": ("x.jpg;id>proof.txt #.jpg", b"whatever", "image/jpeg")}
data = {"name": "Whatever", "category": "Whatever", "description": "Whatever", "price": "9.99"}
requests.post(
    "http://TARGET/api/catalog/products",
    headers={"X-Catalog-Sync-Token": "<token discovered via chatbot>"},
    files=files, data=data,
)
```

(`requests` rather than `curl -F` here specifically because curl's own `-F`
flag uses `;` to separate a field's own attributes — `filename=...;type=...`
— so a literal `;` *inside* the filename value confuses curl's parser. A
library that builds the multipart body directly, or a hand-crafted raw
body, sidesteps that; it's a quirk of the CLI tool, not of the
vulnerability.)

Once the token holder wants an actual reverse shell rather than a proof
file, the same `/`-avoidance constraint applies to the payload command
itself — a real attacker gets around it with a portable, non-bash-specific
trick like `` `pwd|cut -c1` `` (command substitution + `cut`, both POSIX,
both work under `/bin/sh`/dash) to synthesize a `/` character without
typing one literally, then builds an absolute path or a `/dev/tcp/...`
redirect out of that.

## Why this is a good training vulnerability

- Deterministic: no reliance on a specific image-library CVE, no timing,
  nothing version-dependent — `;`-sequencing and `#`-comments in `/bin/sh`
  are exactly the same on every run.
- Realistic shape and realistic bug class: shelling out to a real image
  tool (`convert`) with an attacker-influenced value spliced into the
  command line is precisely the "ImageTragick" family of real-world CVEs
  (ImageMagick/ffmpeg/GraphicsMagick "delegate" command construction
  bugs), not a contrived stand-in — and the normal case (an ordinary
  filename) genuinely produces a working thumbnail, so the feature looks
  and behaves like real functionality, not an obvious trap.
- The `/`-avoidance constraint is itself a real, non-obvious wrinkle: a
  student has to notice that an upstream sanitizer's `os.path.basename()`
  call silently destroys part of their payload before they can build a
  working exploit, then find (or already know) a portable way around it.
- Clearly demonstrates *why* validation layers must agree: each individual
  check here is "reasonable" in isolation (does it look like a jpg? does
  the content-type look right?), and the vulnerability only exists because
  none of them validates the one thing that actually matters once the
  filename reaches a shell: whether it's safe to interpolate unescaped.

## Defensive fix

- Never build a shell command line by string interpolation with any
  attacker-influenced value. Use an argument list (`subprocess.run([...])`,
  no `shell=True`) so arguments are passed directly to the program without
  ever being re-parsed by a shell.
- Validate actual file content (magic-byte sniffing, e.g. `imghdr`/`filetype`
  equivalents, or re-encoding through a trusted image library) rather than
  a substring match on the filename.
- Store uploads under a randomly generated name with no attacker-chosen
  characters at all, and pass that generated name — never the original
  client-supplied filename — to any downstream processing step.
- Run any real image-processing step in a sandboxed, non-shell-invoking
  worker (e.g. a locked-down container/library call, not an external CLI
  tool driven by a hand-built command string).
- Audit every path that reaches a shared processing/storage component,
  not just the one a human uses day to day — a fix applied to one caller
  (the admin upload UI) does nothing for another (the automation
  integration) unless both are actually revisited.
