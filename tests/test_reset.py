from app.models.db import query_all, query_one
from database import seed as seed_module


def test_reset_restores_known_seed_state(client, alice):
    # perturb state: submit a review (indexes into kb) and an extra order
    client.post("/api/products/1/reviews", json={"rating": 1, "body": "temporary perturbation"})
    client.post("/api/orders", json={"product_id": 1, "quantity": 1})

    before_reviews = len(query_all("SELECT id FROM reviews"))
    assert before_reviews >= 3  # 2 seed reviews + the one just added

    seed_module.main()

    after_users = query_all("SELECT username FROM users ORDER BY username")
    assert [u["username"] for u in after_users] == ["alice.customer", "bob.customer"]

    after_reviews = query_all("SELECT id FROM reviews")
    assert len(after_reviews) == 2  # back to exactly the seed reviews

    inc = query_one("SELECT * FROM tickets WHERE ticket_ref = 'INC-10492'")
    assert inc is not None
    assert inc["visibility"] == "internal"

    kb_internal = query_all("SELECT id FROM kb_articles WHERE visibility = 'internal'")
    assert len(kb_internal) == 2
