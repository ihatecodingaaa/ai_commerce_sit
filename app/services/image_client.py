"""Server-side client for the internal image-management microservice
(app/routes/api_images.py). Two legitimate in-app callers use this,
neither of which is part of the lab's vulnerability chain in its own
right: admin ticket screenshots (app/routes/api_admin_tickets.py) and the
catalog-sync product-photo forwarder (app/services/catalog_photos.py).

Holds the current support-image-service credential in-process (via
app/services/credentials.py::get_current_plaintext_for_admin -- the
"trusted server-side code running in the same process" accessor its
docstring describes, warmed at startup by
app/services/rotation.py::ensure_support_image_service_credential) and
issues a real request to the service with it, the same way a real
backend would hold a service API key in its own config/secret store
rather than ship it to a browser. That credential is never rotated on a
timer and never pasted anywhere -- see rotation.py's module docstring --
so /api/images/upload is only ever reachable through this module, not by
an outside caller presenting a leaked token directly.

Self-healing: if the internal call comes back 401 (e.g. someone reseeded
the live database via database/seed.py without restarting this process --
that always writes a fresh random credential, invalidating whatever this
process has cached), _upload()/fetch_screenshot() regenerate the
credential and retry once, rather than failing every request until this
process happens to restart.

Dispatched via current_app.test_client() rather than a real outbound
socket call to our own port: it still goes through the exact same Flask
routing/auth/validation code in app/routes/api_images.py (same headers,
same status codes, same token check against the DB-stored hash) as a
genuine HTTP request would, just without depending on an actual open
listener -- which matters here since this module is exercised the same
way under the test suite as it is in the running container.

See docs/attack-timeline.md Stage 6-9 for the actual vulnerability: it
lives in the catalog-sync-service token (leaked via chat) and the weak
filename check in app/services/catalog_photos.py, not here.
"""
import io

from flask import current_app

from app.services.credentials import get_current_plaintext_for_admin
from app.services.rotation import SUPPORT_IMAGE_SERVICE_NAME, ensure_support_image_service_credential


def _upload(data: bytes, filename: str, content_type: str) -> int | None:
    client = current_app.test_client()

    def attempt(token):
        return client.post(
            "/api/images/upload",
            headers={"X-Service-Token": token},
            data={"file": (io.BytesIO(data), filename, content_type)},
            content_type="multipart/form-data",
        )

    token = get_current_plaintext_for_admin(SUPPORT_IMAGE_SERVICE_NAME)
    resp = attempt(token) if token else None
    if resp is None or resp.status_code == 401:
        # Either this process never cached a credential, or the DB-stored
        # hash no longer matches what we have (e.g. database/seed.py ran
        # against a live DB without this process restarting -- it always
        # writes a fresh random value, invalidating whatever we're holding).
        # Regenerate and retry once instead of failing every request until
        # this process happens to restart.
        token = ensure_support_image_service_credential()
        resp = attempt(token)
    if resp.status_code != 201:
        return None
    return resp.get_json()["image_id"]


def upload_screenshot(file_storage) -> int | None:
    """Upload a browser-supplied file (an admin's ticket-screenshot upload
    form) through support-image-service. Returns the new image_id, or None
    if the upload was rejected.
    """
    return _upload(file_storage.stream.read(), file_storage.filename, file_storage.mimetype)


def upload_screenshot_bytes(data: bytes, filename: str, content_type: str) -> int | None:
    """Same as upload_screenshot, for a caller that already has raw bytes
    and a filename rather than a Flask FileStorage -- e.g.
    app/services/catalog_photos.py, which forwards whatever the
    catalog-sync-token holder submitted, filename (and therefore real
    extension) untouched.
    """
    return _upload(data, filename, content_type)


def fetch_screenshot(image_id: int):
    """Fetch stored image bytes + content type through support-image-service.
    Returns (bytes, content_type), or None if unavailable/not found.
    """
    client = current_app.test_client()

    def attempt(token):
        return client.get(f"/api/images/{image_id}", headers={"X-Service-Token": token})

    token = get_current_plaintext_for_admin(SUPPORT_IMAGE_SERVICE_NAME)
    resp = attempt(token) if token else None
    if resp is None or resp.status_code == 401:
        token = ensure_support_image_service_credential()
        resp = attempt(token)
    if resp.status_code != 200:
        return None
    return resp.data, resp.headers.get("Content-Type", "application/octet-stream")
