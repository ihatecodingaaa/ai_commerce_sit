"""Verifies self-service account editing: scoped to the caller only,
avatar is validated against the fixed preset list (never an arbitrary
value), password changes require the current password, and the account
page shows each user's real role instead of a hardcoded label.
"""
from app.auth import verify_password
from app.models.db import query_one


def test_update_profile_fields(client, alice):
    resp = client.put(
        "/api/account",
        json={"full_name": "Alice Updated", "email": "alice.updated@example-lab.test", "avatar": "owl"},
    )
    assert resp.status_code == 200
    row = query_one("SELECT full_name, email, avatar FROM users WHERE id = ?", (alice["id"],))
    assert row["full_name"] == "Alice Updated"
    assert row["email"] == "alice.updated@example-lab.test"
    assert row["avatar"] == "owl"

    # restore for other tests relying on the seeded login
    client.put(
        "/api/account",
        json={"full_name": alice["full_name"], "email": alice["email"], "avatar": alice["avatar"]},
    )


def test_avatar_must_be_a_known_preset(client, alice):
    resp = client.put(
        "/api/account",
        json={"full_name": alice["full_name"], "email": alice["email"], "avatar": "../../etc/passwd"},
    )
    assert resp.status_code == 400
    row = query_one("SELECT avatar FROM users WHERE id = ?", (alice["id"],))
    assert row["avatar"] == alice["avatar"]


def test_cannot_take_another_customers_email(client, alice):
    # Deliberately not also requesting the `bob` fixture: both fixtures log
    # in on this same shared client, and the second login would silently
    # overwrite the first, so bob's email is looked up directly instead.
    bob_email = query_one("SELECT email FROM users WHERE username = 'bob.customer'")["email"]
    resp = client.put(
        "/api/account",
        json={"full_name": alice["full_name"], "email": bob_email, "avatar": alice["avatar"]},
    )
    assert resp.status_code == 400
    row = query_one("SELECT email FROM users WHERE id = ?", (alice["id"],))
    assert row["email"] == alice["email"]


def test_password_change_requires_correct_current_password(client, alice):
    resp = client.put(
        "/api/account",
        json={
            "full_name": alice["full_name"],
            "email": alice["email"],
            "avatar": alice["avatar"],
            "current_password": "totally-wrong",
            "new_password": "NewPassword123!",
        },
    )
    assert resp.status_code == 400
    row = query_one("SELECT password_hash FROM users WHERE id = ?", (alice["id"],))
    assert row["password_hash"] == alice["password_hash"]


def test_password_change_succeeds_with_correct_current_password(client, alice):
    resp = client.put(
        "/api/account",
        json={
            "full_name": alice["full_name"],
            "email": alice["email"],
            "avatar": alice["avatar"],
            "current_password": "Customer123!",
            "new_password": "BrandNewPassword1!",
        },
    )
    assert resp.status_code == 200
    row = query_one("SELECT password_hash FROM users WHERE id = ?", (alice["id"],))
    assert verify_password("BrandNewPassword1!", row["password_hash"])

    # restore original password so other tests' fixed alice/bob login creds keep working
    client.put(
        "/api/account",
        json={
            "full_name": alice["full_name"],
            "email": alice["email"],
            "avatar": alice["avatar"],
            "current_password": "BrandNewPassword1!",
            "new_password": "Customer123!",
        },
    )


def test_account_edit_requires_login(client):
    resp = client.put("/api/account", json={"full_name": "x", "email": "x@x.test", "avatar": "fox"})
    assert resp.status_code == 401


def test_account_page_shows_admin_role_accurately(client, admin):
    resp = client.get("/account")
    assert resp.status_code == 200
    assert b"Admin" in resp.data
    assert b"<dd>Customer</dd>" not in resp.data


def test_account_page_shows_customer_role_accurately(client, alice):
    resp = client.get("/account")
    assert resp.status_code == 200
    assert b"<dd>Customer</dd>" in resp.data
