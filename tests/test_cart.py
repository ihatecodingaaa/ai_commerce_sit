"""Verifies the cart -> checkout -> order-history flow: adding twice
increments quantity rather than duplicating rows, checkout converts cart
items into real orders and empties the cart, and an empty cart can't be
checked out.
"""
from app.models.db import query_all, query_one


def test_add_to_cart_creates_a_row(client, bob):
    resp = client.post("/api/cart", json={"product_id": 5, "quantity": 1})
    assert resp.status_code == 201
    row = query_one(
        "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = 5", (bob["id"],)
    )
    assert row["quantity"] == 1


def test_adding_same_product_twice_increments_quantity(client, bob):
    client.post("/api/cart", json={"product_id": 6, "quantity": 1})
    client.post("/api/cart", json={"product_id": 6, "quantity": 2})
    rows = query_all("SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = 6", (bob["id"],))
    assert len(rows) == 1
    assert rows[0]["quantity"] == 3


def test_update_and_remove_cart_item(client, bob):
    client.post("/api/cart", json={"product_id": 1, "quantity": 1})
    item = query_one("SELECT id FROM cart_items WHERE user_id = ? AND product_id = 1", (bob["id"],))

    update = client.put(f"/api/cart/{item['id']}", json={"quantity": 5})
    assert update.status_code == 200
    row = query_one("SELECT quantity FROM cart_items WHERE id = ?", (item["id"],))
    assert row["quantity"] == 5

    delete = client.delete(f"/api/cart/{item['id']}")
    assert delete.status_code == 200
    assert query_one("SELECT id FROM cart_items WHERE id = ?", (item["id"],)) is None


def test_checkout_converts_cart_to_orders_and_empties_cart(client, bob):
    # Start from a known-empty cart -- other tests in this session may have
    # left items in bob's cart, since the DB persists across tests.
    for row in query_all("SELECT id FROM cart_items WHERE user_id = ?", (bob["id"],)):
        client.delete(f"/api/cart/{row['id']}")

    client.post("/api/cart", json={"product_id": 2, "quantity": 2})
    client.post("/api/cart", json={"product_id": 3, "quantity": 1})

    resp = client.post("/api/cart/checkout")
    assert resp.status_code == 201
    order_ids = resp.get_json()["order_ids"]
    assert len(order_ids) == 2

    remaining_cart = query_all("SELECT id FROM cart_items WHERE user_id = ?", (bob["id"],))
    assert remaining_cart == []

    orders = query_all("SELECT product_id, quantity, status FROM orders WHERE id IN (%s)" %
                        ",".join(str(i) for i in order_ids))
    assert all(o["status"] == "placed" for o in orders)
    assert {o["product_id"] for o in orders} == {2, 3}


def test_checkout_rejects_empty_cart(client, bob):
    # bob's cart is empty at this point in isolation, but to be certain
    # regardless of execution order, clear it explicitly first.
    for row in query_all("SELECT id FROM cart_items WHERE user_id = ?", (bob["id"],)):
        client.delete(f"/api/cart/{row['id']}")
    resp = client.post("/api/cart/checkout")
    assert resp.status_code == 400


def test_cart_page_requires_login_redirect(client):
    resp = client.get("/cart")
    assert resp.status_code == 302


def test_admin_cannot_view_cart_page(client, admin):
    resp = client.get("/cart")
    assert resp.status_code == 403


def test_admin_cannot_add_to_cart(client, admin):
    resp = client.post("/api/cart", json={"product_id": 1, "quantity": 1})
    assert resp.status_code == 403
    assert query_one("SELECT id FROM cart_items WHERE user_id = ?", (admin["id"],)) is None


def test_admin_cannot_checkout(client, admin):
    resp = client.post("/api/cart/checkout")
    assert resp.status_code == 403


def test_admin_cannot_use_cart_item_endpoints(client, admin):
    assert client.put("/api/cart/1", json={"quantity": 2}).status_code == 403
    assert client.delete("/api/cart/1").status_code == 403
