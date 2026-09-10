"""Verifies review edit/delete is ownership-scoped like every other
customer endpoint, and that the mirrored KB article (the RAG injection
surface) stays in sync with edits and deletions.
"""
from app.models.db import query_all, query_one


def test_owner_can_edit_own_review(app):
    client = app.test_client()
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})

    create = client.post("/api/products/1/reviews", json={"rating": 3, "body": "It's okay."})
    review_id = create.get_json()["review_id"]

    resp = client.put(f"/api/reviews/{review_id}", json={"rating": 5, "body": "Actually it's great!"})
    assert resp.status_code == 200

    row = query_one("SELECT rating, body FROM reviews WHERE id = ?", (review_id,))
    assert row["rating"] == 5
    assert row["body"] == "Actually it's great!"


def test_edit_updates_the_mirrored_kb_article(app):
    client = app.test_client()
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})

    create = client.post("/api/products/1/reviews", json={"rating": 3, "body": "original text marker-aaa"})
    review_id = create.get_json()["review_id"]
    kb_id = create.get_json()["kb_article_id"]

    client.put(f"/api/reviews/{review_id}", json={"rating": 4, "body": "edited text marker-bbb"})

    kb_row = query_one("SELECT body FROM kb_articles WHERE id = ?", (kb_id,))
    assert "marker-bbb" in kb_row["body"]
    assert "marker-aaa" not in kb_row["body"]


def test_other_customer_cannot_edit_your_review(app):
    alice_client = app.test_client()
    alice_client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    create = alice_client.post("/api/products/1/reviews", json={"rating": 5, "body": "alice's honest review"})
    review_id = create.get_json()["review_id"]

    bob_client = app.test_client()
    bob_client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})
    resp = bob_client.put(f"/api/reviews/{review_id}", json={"rating": 1, "body": "tampered by bob"})
    assert resp.status_code == 404

    row = query_one("SELECT rating, body FROM reviews WHERE id = ?", (review_id,))
    assert row["body"] == "alice's honest review"


def test_other_customer_cannot_delete_your_review(app):
    alice_client = app.test_client()
    alice_client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    create = alice_client.post("/api/products/1/reviews", json={"rating": 5, "body": "please don't delete me"})
    review_id = create.get_json()["review_id"]

    bob_client = app.test_client()
    bob_client.post("/login", data={"username": "bob.customer", "password": "Customer123!"})
    resp = bob_client.delete(f"/api/reviews/{review_id}")
    assert resp.status_code == 404

    assert query_one("SELECT id FROM reviews WHERE id = ?", (review_id,)) is not None


def test_owner_delete_removes_review_and_kb_article(app):
    client = app.test_client()
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    create = client.post("/api/products/1/reviews", json={"rating": 5, "body": "temporary review"})
    review_id = create.get_json()["review_id"]
    kb_id = create.get_json()["kb_article_id"]

    resp = client.delete(f"/api/reviews/{review_id}")
    assert resp.status_code == 200

    assert query_one("SELECT id FROM reviews WHERE id = ?", (review_id,)) is None
    assert query_one("SELECT id FROM kb_articles WHERE id = ?", (kb_id,)) is None


def test_edit_delete_require_login(client):
    assert client.put("/api/reviews/1", json={"rating": 5, "body": "x"}).status_code == 401
    assert client.delete("/api/reviews/1").status_code == 401
