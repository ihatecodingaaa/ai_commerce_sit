"""Internal image-management API.

Represents a small internal microservice used by two in-app callers, both
going through app/services/image_client.py: admin ticket screenshots and
the catalog-sync product-photo forwarder (app/services/catalog_photos.py).
Authorization is a single shared bearer token (support-image-service),
not a customer session -- intentionally a *different, narrower* trust
boundary than the customer-facing API (see docs/architecture.md).

That token is never rotated on a timer and never pasted anywhere (see
app/services/rotation.py), so -- unlike in earlier versions of this lab --
this route is NOT directly reachable by an outside attacker presenting a
leaked value; only this app's own backend ever holds it. It is still,
however, where the real vulnerability's *effect* lands:

  1. This API validates the client-supplied `Content-Type` of the multipart
     part -- a header fully controlled by whoever originally submitted the
     file -- instead of the filename extension or the actual file bytes.
  2. Storage keeps the original filename (minus path separators), so the
     extension the *processing* stage will trust is whatever that
     original submitter named the file.
  3. app/../vulnerable/upload/image_processor.py decides what to do based
     on that filename extension: a `.py` file is imported and executed.

Both of those attacker-controlled values (Content-Type, filename) arrive
here untouched from whatever the catalog-sync-service-token holder
originally submitted to app/routes/api_catalog.py -- see that module and
vulnerable/upload/README.md for the actual entry point and full writeup.
"""
import os
import uuid

from flask import Blueprint, jsonify, request, send_from_directory

from app.config import config
from app.logging_setup import log_event
from app.models.db import execute, query_all, query_one
from app.services.credentials import verify as verify_service_token
from app.services.rotation import SUPPORT_IMAGE_SERVICE_NAME
from vulnerable.upload.image_processor import process_uploaded_image

bp = Blueprint("api_images", __name__, url_prefix="/api/images")

# Step 1: validated against the client-supplied Content-Type header, not
# the actual file. This is the deliberate gap.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _require_service_token():
    # Real verification: hash whatever was presented and compare to the
    # stored hash for support-image-service (see app/services/credentials.py).
    # This credential is generated once per process
    # (app/services/rotation.py::ensure_support_image_service_credential)
    # and never disclosed, so only this app's own backend
    # (app/services/image_client.py) ever presents it.
    token = request.headers.get("X-Service-Token", "")
    if not verify_service_token(SUPPORT_IMAGE_SERVICE_NAME, token):
        log_event(
            "service_token_auth_failed",
            request_id=uuid.uuid4().hex[:12],
            token=token or "(none)",
        )
        return False
    return True


def _weak_sanitize_filename(filename: str) -> str:
    """Strips directory components but -- deliberately -- keeps the
    extension exactly as supplied. This is step 2 of the disagreement
    documented above: storage trusts whatever extension the original
    submitter chose.
    """
    base = os.path.basename(filename or "upload.bin")
    base = base.replace("..", "_")
    return base or "upload.bin"


@bp.route("/upload", methods=["POST"])
def upload_image():
    request_id = uuid.uuid4().hex[:12]
    if not _require_service_token():
        return jsonify({"error": "invalid or missing service token"}), 401

    log_event("service_token_used", request_id=request_id, action="upload")

    if "file" not in request.files:
        return jsonify({"error": "file field is required"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    claimed_type = file.mimetype or file.content_type or ""
    if claimed_type not in ALLOWED_CONTENT_TYPES:
        log_event(
            "image_upload_rejected",
            request_id=request_id,
            filename=file.filename,
            claimed_type=claimed_type,
            reason="content_type_not_allowed",
        )
        return jsonify({"error": f"content type '{claimed_type}' not allowed"}), 400

    filename = _weak_sanitize_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    stored_path = os.path.join(config.UPLOAD_DIR, stored_name)

    data = file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"error": "file too large"}), 400

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    with open(stored_path, "wb") as fh:
        fh.write(data)

    image_id = execute(
        "INSERT INTO images (filename, stored_path, claimed_content_type, size_bytes) VALUES (?, ?, ?, ?)",
        (filename, stored_path, claimed_type, len(data)),
    )
    log_event(
        "image_uploaded",
        request_id=request_id,
        image_id=image_id,
        filename=filename,
        claimed_type=claimed_type,
        size_bytes=len(data),
    )

    processing_result = process_uploaded_image(stored_path, request_id=request_id)

    return (
        jsonify({"image_id": image_id, "filename": filename, "processing": processing_result}),
        201,
    )


@bp.route("", methods=["GET"])
def list_images():
    if not _require_service_token():
        return jsonify({"error": "invalid or missing service token"}), 401
    log_event("service_token_used", request_id=uuid.uuid4().hex[:12], action="list")
    rows = query_all(
        "SELECT id, filename, claimed_content_type, size_bytes, created_at FROM images ORDER BY id DESC"
    )
    return jsonify({"images": rows})


@bp.route("/<int:image_id>", methods=["GET"])
def get_image(image_id):
    if not _require_service_token():
        return jsonify({"error": "invalid or missing service token"}), 401
    log_event("service_token_used", request_id=uuid.uuid4().hex[:12], action="get", image_id=image_id)

    row = query_one("SELECT stored_path FROM images WHERE id = ?", (image_id,))
    if not row:
        return jsonify({"error": "not found"}), 404

    directory = os.path.dirname(row["stored_path"])
    basename = os.path.basename(row["stored_path"])
    return send_from_directory(directory, basename)
