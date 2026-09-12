"""Verifies the customer-facing ticket-photo attachment feature
(app/services/ticket_photos.py, app/routes/api_support.py):

  1. Content is validated by real magic bytes, never by filename or
     Content-Type -- the same secure pattern as admin product photos
     (app/services/product_photos.py), and the deliberate contrast with
     vulnerable/upload/image_processor.py and
     app/services/catalog_photos.py.
  2. It's scoped to the caller's own ticket -- one customer can never
     upload to, or view, another customer's ticket photo.
  3. It never touches the internal image-management service
     (app/routes/api_images.py) or its vulnerable processing step.
"""
import io

from app.models.db import query_one

# Minimal real magic-byte header -- the sniffer only inspects these first
# bytes (app/services/image_validation.py), so a short buffer is enough to
# prove content-based detection without needing a fully valid image file.
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _create_ticket(client) -> int:
    resp = client.post("/api/tickets", json={"subject": "Broken widget", "body": "It arrived cracked."})
    assert resp.status_code == 201
    row = query_one(
        "SELECT id FROM tickets WHERE ticket_ref = ?", (resp.get_json()["ticket_ref"],)
    )
    return row["id"]


def test_customer_can_attach_a_real_photo_to_their_own_ticket(client, alice):
    ticket_id = _create_ticket(client)

    resp = client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201

    row = query_one("SELECT customer_photo_path FROM tickets WHERE id = ?", (ticket_id,))
    assert row["customer_photo_path"]
    assert row["customer_photo_path"].endswith(".jpg")

    fetched = client.get(f"/api/tickets/{ticket_id}/photo")
    assert fetched.status_code == 200
    assert fetched.data == JPEG_HEADER


def test_ticket_photo_upload_rejects_content_that_is_not_really_an_image(client, alice):
    ticket_id = _create_ticket(client)

    # Claims to be a jpeg via filename AND Content-Type, but the actual
    # bytes are plain text -- the sniffer must reject it on content alone,
    # exactly like app/services/product_photos.py does.
    resp = client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(b"not actually an image"), "photo.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400

    row = query_one("SELECT customer_photo_path FROM tickets WHERE id = ?", (ticket_id,))
    assert row["customer_photo_path"] is None


def test_ticket_photo_upload_rejects_a_disguised_python_payload(client, alice):
    ticket_id = _create_ticket(client)

    # The exact shape of the lab's Stage 8 payload (double extension,
    # image/jpeg Content-Type) -- must be rejected here on content, unlike
    # app/services/catalog_photos.py's deliberately weak check.
    payload = b"import os\nos.system('id')\n"
    resp = client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(payload), "plugin.jpg.py", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_customer_cannot_upload_to_another_customers_ticket(client, alice):
    ticket_id = _create_ticket(client)  # created while logged in as alice

    client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})
    resp = client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404

    row = query_one("SELECT customer_photo_path FROM tickets WHERE id = ?", (ticket_id,))
    assert row["customer_photo_path"] is None


def test_customer_cannot_view_another_customers_ticket_photo(client, alice):
    ticket_id = _create_ticket(client)
    client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )

    client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})
    resp = client.get(f"/api/tickets/{ticket_id}/photo")
    assert resp.status_code == 404


def test_support_tickets_page_renders_upload_ui_and_photo(client, alice):
    ticket_id = _create_ticket(client)
    resp = client.get("/support/tickets")
    assert resp.status_code == 200
    assert b"upload-ticket-photo" in resp.data
    assert b"Attach a photo" in resp.data

    client.post(
        f"/api/tickets/{ticket_id}/photo",
        data={"file": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    resp = client.get("/support/tickets")
    assert f"/api/tickets/{ticket_id}/photo".encode() in resp.data


def test_ticket_photo_upload_requires_login(client):
    resp = client.post(
        "/api/tickets/1/photo",
        data={"file": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401
