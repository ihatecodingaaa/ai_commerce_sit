"""Verifies the customer-facing side of ticket screenshots: a customer can
attach a photo to their OWN ticket and read it back, another customer can't
reach it, an anonymous caller can't either, and an admin (who didn't upload
it) can still view it read-only through the admin-only counterpart route.

This is the legitimate, customer-facing entry point into
support-image-service, parallel to the admin-only one in
tests/test_admin_tickets.py -- both call through
app/services/image_client.py using the same in-process credential, and
neither ever exposes the token itself to a browser.

Logins are done explicitly (not via the alice/bob/admin fixtures) because
several tests need to switch sessions *within* the test body, after the
ticket already exists -- fixture instantiation order isn't something to
depend on for that.
"""
import io

from app.models.db import query_one

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _create_ticket_as_alice(client):
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    resp = client.post("/api/tickets", json={"subject": "Broken earbuds", "body": "left one is dead"})
    return resp.get_json()["ticket_ref"]


def test_customer_can_attach_and_fetch_own_ticket_screenshot(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))

    resp = client.post(
        f"/api/tickets/{ticket['id']}/screenshot",
        data={"file": (io.BytesIO(_PNG_BYTES), "defect.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    image_id = resp.get_json()["image_id"]

    row = query_one("SELECT customer_screenshot_image_id FROM tickets WHERE id = ?", (ticket["id"],))
    assert row["customer_screenshot_image_id"] == image_id

    resp = client.get(f"/api/tickets/{ticket['id']}/screenshot")
    assert resp.status_code == 200
    assert resp.data == _PNG_BYTES


def test_other_customer_cannot_reach_ticket_screenshot(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))

    client.post("/logout")
    client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})

    resp = client.post(
        f"/api/tickets/{ticket['id']}/screenshot",
        data={"file": (io.BytesIO(_PNG_BYTES), "defect.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404
    resp = client.get(f"/api/tickets/{ticket['id']}/screenshot")
    assert resp.status_code == 404


def test_anonymous_cannot_reach_ticket_screenshot(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))
    client.post("/logout")

    resp = client.post(
        f"/api/tickets/{ticket['id']}/screenshot",
        data={"file": (io.BytesIO(_PNG_BYTES), "defect.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401
    resp = client.get(f"/api/tickets/{ticket['id']}/screenshot")
    assert resp.status_code == 401


def test_admin_can_view_customer_screenshot_readonly(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))
    client.post(
        f"/api/tickets/{ticket['id']}/screenshot",
        data={"file": (io.BytesIO(_PNG_BYTES), "defect.png", "image/png")},
        content_type="multipart/form-data",
    )

    client.post("/logout")
    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    resp = client.get(f"/api/admin/tickets/{ticket['id']}/customer-screenshot")
    assert resp.status_code == 200
    assert resp.data == _PNG_BYTES


def test_customer_cannot_reach_admin_customer_screenshot_route(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))

    resp = client.get(f"/api/admin/tickets/{ticket['id']}/customer-screenshot")
    assert resp.status_code == 403
