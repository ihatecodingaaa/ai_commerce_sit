"""Verifies ordinary customer endpoints/tools are properly scoped, so the
chatbot vulnerability tested elsewhere is not just "everything is
unauthenticated".
"""
from app.tools.customer_lookup import customer_lookup
from app.tools.order_lookup import order_lookup
from app.tools.ticket_search import ticket_search


def test_cart_page_requires_login(client):
    resp = client.get("/cart")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_cart_api_requires_login(client):
    resp = client.post("/api/cart", json={"product_id": 1, "quantity": 1})
    assert resp.status_code == 401


def test_chat_api_requires_login(client):
    resp = client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_order_lookup_tool_is_scoped_to_caller(alice, bob):
    # alice's orders must not include bob's, and vice versa.
    alice_orders = order_lookup(user_id=alice["id"])["orders"]
    bob_orders = order_lookup(user_id=bob["id"])["orders"]

    alice_ids = {o["id"] for o in alice_orders}
    bob_ids = {o["id"] for o in bob_orders}
    assert alice_ids.isdisjoint(bob_ids)
    assert len(alice_orders) > 0
    assert len(bob_orders) > 0


def test_customer_lookup_tool_cannot_target_other_customer(alice, bob):
    # The tool signature has no parameter for "which customer" -- it always
    # returns the bound caller's own profile.
    result = customer_lookup(user_id=alice["id"])
    assert result["customer"]["id"] == alice["id"]
    assert result["customer"]["username"] == "alice.customer"


def test_ticket_search_excludes_internal_tickets(alice):
    # Customer-scoped ticket_search must never surface internal engineering
    # tickets, even when queried with terms that would match them.
    result = ticket_search(user_id=alice["id"], query="support-image-service")
    refs = [t["ticket_ref"] for t in result["tickets"]]
    assert "INC-10492" not in refs
    assert "INC-10480" not in refs


def test_review_submission_requires_login(client):
    resp = client.post("/api/products/1/reviews", json={"rating": 5, "body": "nice"})
    assert resp.status_code == 401


def test_cannot_modify_another_customers_cart_item(client):
    # Alice adds an item, then bob (a separate login on the same shared
    # test client) must not be able to touch that cart row by id.
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    add = client.post("/api/cart", json={"product_id": 2, "quantity": 1})
    assert add.status_code == 201
    from app.models.db import query_one

    alice_item = query_one(
        "SELECT c.id FROM cart_items c JOIN users u ON u.id = c.user_id "
        "WHERE u.username = 'alice.customer' AND c.product_id = 2"
    )

    client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})
    resp = client.put(f"/api/cart/{alice_item['id']}", json={"quantity": 99})
    assert resp.status_code == 404
    resp = client.delete(f"/api/cart/{alice_item['id']}")
    assert resp.status_code == 404
