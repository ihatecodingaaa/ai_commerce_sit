"""DELIBERATELY VULNERABLE component. See vulnerable/upload/README.md.

Simulates a lightweight "image processing worker" for the internal image
API. A real deployment would run this out-of-process (a queue worker); for
lab simplicity it runs synchronously right after upload from
app/routes/api_images.py.

It supports a "custom filter plugin" feature: any file ending in .py that
ends up in the upload directory is treated as a filter plugin and is
imported, which executes the file's top-level code (and its apply()
function, if defined). This is a plausible internal feature -- teams really
do build "upload a custom filter/theme" extensibility -- that becomes
remote code execution because the upload API validates the client-supplied
Content-Type header rather than the real file type, so a file can be named
and typed as a "processing plugin" while APPEARING to satisfy an
"image upload" check. See app/routes/api_images.py for the validation gap.
"""
import importlib.util
import os

from app.logging_setup import log_event

PLUGIN_EXTENSION = ".py"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


def process_uploaded_image(filepath: str, request_id: str = "") -> dict:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == PLUGIN_EXTENSION:
        log_event("image_processing_plugin_load", path=filepath, request_id=request_id)
        _load_and_run_plugin(filepath, request_id)
        return {"processed": True, "mode": "plugin"}

    if ext in IMAGE_EXTENSIONS:
        # Lab stand-in for real thumbnailing; deliberately has no image
        # library dependency so the lab stays lightweight on a 4 GiB host.
        log_event("image_processed", path=filepath, request_id=request_id, mode="thumbnail")
        return {"processed": True, "mode": "thumbnail"}

    log_event("image_processing_skipped", path=filepath, request_id=request_id, reason="unrecognized_extension")
    return {"processed": False, "mode": "skipped"}


def _load_and_run_plugin(filepath: str, request_id: str):
    spec = importlib.util.spec_from_file_location("uploaded_filter_plugin", filepath)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # <-- arbitrary code execution, as the app process user
        if hasattr(module, "apply"):
            module.apply()
    except Exception as exc:  # noqa: BLE001 - lab worker must not crash the request
        log_event("image_plugin_apply_error", path=filepath, error=str(exc), request_id=request_id)
