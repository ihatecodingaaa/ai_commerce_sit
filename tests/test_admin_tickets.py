"""Verifies admin can view and update customer support tickets (status +
a reply), scoped correctly (customer-visibility tickets only, never the
internal engineering tickets), and that a customer session can never
reach the admin ticket endpoints.
"""
from app.models.db import query_one


def _create_ticket_as_alice(client):
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    resp = client.post("/api/tickets", json={"subject": "Admin test ticket", "body": "please help"})
    assert resp.status_code == 201
    return resp.get_json()["ticket_ref"]


def test_admin_tickets_page_requires_admin(client, alice):
    resp = client.get("/admin/tickets")
    assert resp.status_code == 403


def test_admin_can_view_all_customer_tickets(client):
    ref = _create_ticket_as_alice(client)
    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    resp = client.get("/admin/tickets")
    assert resp.status_code == 200
    assert ref.encode() in resp.data


def test_admin_tickets_view_excludes_internal_tickets(client):
    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    resp = client.get("/admin/tickets")
    assert b"INC-10492" not in resp.data
    assert b"INC-10480" not in resp.data


def test_admin_can_update_status_and_reply(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))

    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    resp = client.put(
        f"/api/admin/tickets/{ticket['id']}",
        json={"status": "resolved", "admin_reply": "All set, thanks for reaching out!"},
    )
    assert resp.status_code == 200

    row = query_one("SELECT status, admin_reply FROM tickets WHERE id = ?", (ticket["id"],))
    assert row["status"] == "resolved"
    assert row["admin_reply"] == "All set, thanks for reaching out!"


def test_customer_sees_admin_reply_on_their_ticket_page(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))

    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    client.put(f"/api/admin/tickets/{ticket['id']}", json={"status": "in_progress", "admin_reply": "Looking into it."})

    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    resp = client.get("/support/tickets")
    assert b"Looking into it." in resp.data


def test_customer_cannot_update_tickets(client, alice):
    ticket = query_one("SELECT id FROM tickets LIMIT 1")
    resp = client.put(f"/api/admin/tickets/{ticket['id']}", json={"status": "resolved"})
    assert resp.status_code == 403


def test_invalid_status_rejected(client):
    ref = _create_ticket_as_alice(client)
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ref,))
    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    resp = client.put(f"/api/admin/tickets/{ticket['id']}", json={"status": "not-a-real-status"})
    assert resp.status_code == 400
