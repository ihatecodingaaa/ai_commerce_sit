"""Verifies the admin product-management boundary: only role='admin'
accounts can reach it, self-registration can never create one, and a
product delete correctly cascades to its dependent rows.
"""
from app.models.db import query_all, query_one


def test_self_registration_is_always_role_customer(client):
    client.post(
        "/register",
        data={
            "username": "newperson",
            "email": "newperson@example-lab.test",
            "full_name": "New Person",
            "password": "Sup3rSecret!",
        },
    )
    row = query_one("SELECT role FROM users WHERE username = 'newperson'")
    assert row["role"] == "customer"


def test_admin_page_requires_login(client):
    resp = client.get("/admin/products")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_page_forbidden_for_customer(alice, client):
    resp = client.get("/admin/products")
    assert resp.status_code == 403


def test_admin_page_reachable_for_admin(admin, client):
    resp = client.get("/admin/products")
    assert resp.status_code == 200


def test_admin_api_rejects_unauthenticated(client):
    resp = client.post("/api/admin/products", json={"name": "x", "category": "y", "price": 1, "description": "z"})
    assert resp.status_code == 401


def test_admin_api_rejects_customer(client, alice):
    resp = client.post(
        "/api/admin/products",
        json={"name": "Sneaky Product", "category": "Test", "price": 9.99, "description": "should not be created"},
    )
    assert resp.status_code == 403
    assert query_one("SELECT id FROM products WHERE name = 'Sneaky Product'") is None


def test_admin_can_create_edit_delete_product(client, admin):
    create = client.post(
        "/api/admin/products",
        json={"name": "Test Widget", "category": "Gadgets", "price": 19.99, "description": "A widget for testing."},
    )
    assert create.status_code == 201
    product_id = create.get_json()["product_id"]

    row = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    assert row["name"] == "Test Widget"
    assert row["price_cents"] == 1999

    update = client.put(
        f"/api/admin/products/{product_id}",
        json={"name": "Updated Widget", "category": "Gadgets", "price": 24.5, "description": "Now improved."},
    )
    assert update.status_code == 200
    row = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    assert row["name"] == "Updated Widget"
    assert row["price_cents"] == 2450

    delete = client.delete(f"/api/admin/products/{product_id}")
    assert delete.status_code == 200
    assert query_one("SELECT id FROM products WHERE id = ?", (product_id,)) is None


def test_admin_create_rejects_invalid_price(client, admin):
    resp = client.post(
        "/api/admin/products",
        json={"name": "Bad Price", "category": "Test", "price": "not-a-number", "description": "x"},
    )
    assert resp.status_code == 400


def test_deleting_product_cascades_reviews_kb_and_orders(client):
    # One shared test client, logging in as different users at different
    # points -- clearer than stacking fixtures whose login side effects
    # would just overwrite each other's session in an unpredictable order.
    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    create = client.post(
        "/api/admin/products",
        json={"name": "Cascade Test Product", "category": "Test", "price": 5.0, "description": "for cascade test"},
    )
    product_id = create.get_json()["product_id"]

    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    order_resp = client.post("/api/orders", json={"product_id": product_id, "quantity": 1})
    assert order_resp.status_code == 201
    review_resp = client.post(
        f"/api/products/{product_id}/reviews", json={"rating": 5, "body": "cascade delete test review"}
    )
    assert review_resp.status_code == 201
    review_id = review_resp.get_json()["review_id"]
    kb_id = review_resp.get_json()["kb_article_id"]

    client.post("/login", data={"username": "admin", "password": "AdminLab123!"})
    delete = client.delete(f"/api/admin/products/{product_id}")
    assert delete.status_code == 200

    assert query_one("SELECT id FROM products WHERE id = ?", (product_id,)) is None
    assert query_one("SELECT id FROM reviews WHERE id = ?", (review_id,)) is None
    assert query_one("SELECT id FROM kb_articles WHERE id = ?", (kb_id,)) is None
    assert query_all("SELECT id FROM orders WHERE product_id = ?", (product_id,)) == []
