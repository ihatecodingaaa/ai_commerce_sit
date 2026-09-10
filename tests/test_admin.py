"""Verifies the admin product-management boundary: only role='admin'
accounts can reach it, self-registration can never create one, and a
product delete correctly cascades to its dependent rows.
"""
import io
import os

from app.config import config
from app.models.db import query_all, query_one

# Minimal real magic-byte headers -- the sniffer only inspects these first
# bytes (app/services/product_photos.py), so a short buffer is enough to
# prove content-based detection without needing a fully valid image file.
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 32


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
    cart_resp = client.post("/api/cart", json={"product_id": product_id, "quantity": 1})
    assert cart_resp.status_code == 201
    checkout_resp = client.post("/api/cart/checkout")
    assert checkout_resp.status_code == 201
    # a second cart entry that's never checked out, to prove cart_items
    # (not just orders) get cascaded too
    cart_resp2 = client.post("/api/cart", json={"product_id": product_id, "quantity": 2})
    assert cart_resp2.status_code == 201
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
    assert query_all("SELECT id FROM cart_items WHERE product_id = ?", (product_id,)) == []


# --- Product photos -------------------------------------------------------
# Deliberately contrasts with tests/test_upload_vuln.py: this upload path
# sniffs real file content and picks its own extension, so the same
# "claim image/jpeg, actually a .py file" trick that works against
# /api/images/upload must NOT work here.


def test_admin_can_upload_a_real_product_photo(client, admin):
    resp = client.post(
        "/api/admin/products",
        data={
            "name": "Photographed Widget",
            "category": "Test",
            "price": "12.00",
            "description": "has a real photo",
            "photo": (io.BytesIO(PNG_HEADER), "whatever.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["image_path"].endswith(".png")

    row = query_one("SELECT image_path FROM products WHERE id = ?", (body["product_id"],))
    assert row["image_path"] == body["image_path"]
    assert os.path.exists(os.path.join(config.PRODUCT_PHOTO_DIR, row["image_path"]))


def test_photo_extension_is_chosen_by_sniffing_not_by_filename(client, admin):
    """The stored filename's extension must reflect the sniffed content,
    not whatever extension the client's filename happened to have."""
    resp = client.post(
        "/api/admin/products",
        data={
            "name": "Mislabeled Extension Widget",
            "category": "Test",
            "price": "12.00",
            "description": "jpeg bytes in a .png-named file",
            "photo": (io.BytesIO(JPEG_HEADER), "photo.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["image_path"].endswith(".jpg")


def test_disguised_non_image_upload_is_rejected(client, admin):
    """The same trick that defeats /api/images/upload (name it .jpg, claim
    Content-Type: image/jpeg, actually ship a script) must be rejected
    here, because this endpoint checks real file content instead."""
    payload = b"import os\nos.system('id')\n"
    resp = client.post(
        "/api/admin/products",
        data={
            "name": "Malicious Product",
            "category": "Test",
            "price": "12.00",
            "description": "should be rejected",
            "photo": (io.BytesIO(payload), "evil.py", "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert query_one("SELECT id FROM products WHERE name = 'Malicious Product'") is None


def test_non_admin_cannot_upload_product_photo(client, alice):
    resp = client.post(
        "/api/admin/products",
        data={
            "name": "Sneaky Photo Product",
            "category": "Test",
            "price": "12.00",
            "description": "should not be created",
            "photo": (io.BytesIO(PNG_HEADER), "x.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403


def test_product_photo_is_servable(client, admin):
    create = client.post(
        "/api/admin/products",
        data={
            "name": "Servable Widget",
            "category": "Test",
            "price": "8.00",
            "description": "served over HTTP",
            "photo": (io.BytesIO(PNG_HEADER), "x.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    image_path = create.get_json()["image_path"]

    # Public route -- a logged-out visitor browsing the storefront must
    # still be able to load product photos.
    anon_client = client.application.test_client()
    resp = anon_client.get(f"/product-photos/{image_path}")
    assert resp.status_code == 200
    assert resp.data.startswith(b"\x89PNG")


def test_editing_product_replaces_old_photo_file(client, admin):
    create = client.post(
        "/api/admin/products",
        data={
            "name": "Replaceable Widget",
            "category": "Test",
            "price": "8.00",
            "description": "original photo",
            "photo": (io.BytesIO(PNG_HEADER), "x.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    product_id = create.get_json()["product_id"]
    old_path = create.get_json()["image_path"]
    old_full_path = os.path.join(config.PRODUCT_PHOTO_DIR, old_path)
    assert os.path.exists(old_full_path)

    update = client.put(
        f"/api/admin/products/{product_id}",
        data={
            "name": "Replaceable Widget",
            "category": "Test",
            "price": "8.00",
            "description": "new photo",
            "photo": (io.BytesIO(JPEG_HEADER), "x.jpg", "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    new_path = update.get_json()["image_path"]

    assert new_path != old_path
    assert not os.path.exists(old_full_path), "old photo file should have been deleted on replacement"
    assert os.path.exists(os.path.join(config.PRODUCT_PHOTO_DIR, new_path))


def test_removing_photo_via_remove_flag(client, admin):
    create = client.post(
        "/api/admin/products",
        data={
            "name": "Removable Photo Widget",
            "category": "Test",
            "price": "8.00",
            "description": "will lose its photo",
            "photo": (io.BytesIO(PNG_HEADER), "x.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    product_id = create.get_json()["product_id"]
    old_path = create.get_json()["image_path"]

    update = client.put(
        f"/api/admin/products/{product_id}",
        data={
            "name": "Removable Photo Widget",
            "category": "Test",
            "price": "8.00",
            "description": "no more photo",
            "remove_photo": "true",
        },
        content_type="multipart/form-data",
    )
    assert update.status_code == 200
    assert update.get_json()["image_path"] is None
    assert not os.path.exists(os.path.join(config.PRODUCT_PHOTO_DIR, old_path))


def test_deleting_product_removes_its_photo_file(client, admin):
    create = client.post(
        "/api/admin/products",
        data={
            "name": "Doomed Widget",
            "category": "Test",
            "price": "8.00",
            "description": "about to be deleted",
            "photo": (io.BytesIO(PNG_HEADER), "x.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    product_id = create.get_json()["product_id"]
    image_path = create.get_json()["image_path"]
    full_path = os.path.join(config.PRODUCT_PHOTO_DIR, image_path)
    assert os.path.exists(full_path)

    client.delete(f"/api/admin/products/{product_id}")
    assert not os.path.exists(full_path)


def test_photo_serving_route_rejects_path_traversal(client):
    resp = client.get("/product-photos/..%2f..%2f..%2fetc%2fpasswd")
    assert resp.status_code in (400, 404)
