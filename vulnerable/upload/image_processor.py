"""DELIBERATELY VULNERABLE component. See vulnerable/upload/README.md.

Simulates a lightweight "image processing worker" for the internal image
API. A real deployment would run this out-of-process (a queue worker); for
lab simplicity it runs synchronously right after upload from
app/routes/api_images.py.

THE BUG (intentional, for training): CWE-78, OS Command Injection. Thumbnail
generation shells out to ImageMagick's `convert` by building the command
line as an f-string that embeds the uploaded file's own on-disk path --
which is derived directly from whatever filename the client supplied,
completely unescaped (see app/routes/api_images.py::_weak_sanitize_filename,
which strips directory separators but never touches shell metacharacters).
A normal filename produces a normal thumbnail -- the feature genuinely
works, which is exactly what makes this realistic. A filename containing
`;`, `|`, backticks, or `$(...)` breaks out of the intended `convert`
invocation and runs arbitrary shell code instead. This mirrors a real,
still-current vulnerability class: ImageMagick/ffmpeg/GraphicsMagick
"delegate" command-construction bugs (the 2016 "ImageTragick" family, and
many descendants since) are exactly this shape -- a trusted-looking image
tool invoked via a shell string built from attacker-influenced input.
"""
import os
import subprocess

from app.logging_setup import log_event

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")
THUMBNAIL_SUFFIX = "_thumb"


def process_uploaded_image(filepath: str, request_id: str = "") -> dict:
    ext = os.path.splitext(filepath)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return _generate_thumbnail(filepath, request_id)

    log_event("image_processing_skipped", path=filepath, request_id=request_id, reason="unrecognized_extension")
    return {"processed": False, "mode": "skipped"}


def _generate_thumbnail(filepath: str, request_id: str) -> dict:
    base, ext = os.path.splitext(filepath)
    thumb_path = f"{base}{THUMBNAIL_SUFFIX}{ext}"
    upload_dir = os.path.dirname(filepath)

    # <-- THE BUG: filepath (attacker-influenced, see module docstring) is
    # interpolated directly into a shell command string with no quoting.
    # subprocess.run(..., shell=True) hands this whole string to /bin/sh,
    # so shell metacharacters inside filepath are interpreted by the shell
    # before `convert` ever sees its arguments. Running with cwd=upload_dir
    # (a plausible, ordinary choice -- keep intermediate/temp files inside
    # the upload directory rather than wherever the app process happens to
    # be running from) also means any relative-path command an attacker
    # injects lands inside a predictable, known location.
    command = f"convert {filepath} -resize 128x128 {thumb_path}"
    log_event("image_processing_thumbnail_started", path=filepath, request_id=request_id)
    try:
        subprocess.run(command, shell=True, timeout=15, capture_output=True, cwd=upload_dir)
    except Exception as exc:  # noqa: BLE001 - lab worker must not crash the request
        log_event("image_processing_error", path=filepath, error=str(exc), request_id=request_id)
        return {"processed": False, "mode": "thumbnail_failed"}

    log_event("image_processed", path=filepath, request_id=request_id, mode="thumbnail")
    return {"processed": True, "mode": "thumbnail"}
