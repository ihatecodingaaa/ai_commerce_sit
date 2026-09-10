"""Server-side client for the internal image-management microservice
(app/routes/api_images.py), used by admin-facing features that need to
store or read an image through that service.

This is the legitimate way something inside our own backend is meant to
reach support-image-service: hold the current credential in-process (via
app/services/credentials.py::get_current_plaintext_for_admin -- the
"trusted server-side code running in the same process" accessor its
docstring describes) and issue a real request to the service with it, the
same way a real backend would hold a service API key in its own config/
secret store rather than ship it to a browser. The browser never sees the
token; it only ever talks to the admin-session-gated routes in
app/routes/api_admin_tickets.py.

Dispatched via current_app.test_client() rather than a real outbound
socket call to our own port: it still goes through the exact same Flask
routing/auth/validation code in app/routes/api_images.py (same headers,
same status codes, same token check against the DB-stored hash) as a
genuine HTTP request would, just without depending on an actual open
listener -- which matters here since this module is exercised the same
way under the test suite as it is in the running container.

Nothing here changes what makes /api/images/upload vulnerable -- the
token itself still doesn't distinguish "this app's own backend" from
"anyone who has the value", which is exactly why leaking it (see
docs/attack-timeline.md Stage 6) grants the same access this module has.
"""
from flask import current_app

from app.services.credentials import get_current_plaintext_for_admin
from app.services.rotation import SERVICE_NAME


def upload_screenshot(file_storage) -> int | None:
    """Upload an admin-supplied file through support-image-service.
    Returns the new image_id, or None if the current service credential
    isn't available in-process or the upload was rejected.
    """
    token = get_current_plaintext_for_admin(SERVICE_NAME)
    if not token:
        return None
    client = current_app.test_client()
    resp = client.post(
        "/api/images/upload",
        headers={"X-Service-Token": token},
        data={"file": (file_storage.stream, file_storage.filename, file_storage.mimetype)},
        content_type="multipart/form-data",
    )
    if resp.status_code != 201:
        return None
    return resp.get_json()["image_id"]


def fetch_screenshot(image_id: int):
    """Fetch stored image bytes + content type through support-image-service.
    Returns (bytes, content_type), or None if unavailable/not found.
    """
    token = get_current_plaintext_for_admin(SERVICE_NAME)
    if not token:
        return None
    client = current_app.test_client()
    resp = client.get(f"/api/images/{image_id}", headers={"X-Service-Token": token})
    if resp.status_code != 200:
        return None
    return resp.data, resp.headers.get("Content-Type", "application/octet-stream")
