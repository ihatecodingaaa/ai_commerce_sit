"""Catalog-sync integration: lets the warehouse/inventory system push new
products directly, authenticated with a shared bearer token
(X-Catalog-Sync-Token) instead of an admin session -- a machine-to-machine
integration with no human present, the same shape as
app/routes/api_images.py's support-image-service token, just for a
different internal service.

Intentionally a *separate* trust boundary from the admin session
(app/routes/api_admin.py is the human-facing equivalent) -- a customer
session, no matter whose, never reaches this either way, since this
route checks only the token and never looks at cookies at all.

This token itself is fine to exist -- an automation client with no human
in the loop is a completely ordinary thing for a catalog to have. The
lab's actual vulnerability is what this route lets a token holder submit
unchecked: see app/services/catalog_photos.py for the weak photo check,
and docs/attack-timeline.md Stage 6-9 for the full chain (the token is
disclosed via chat, exactly like support-image-service's used to be).
"""
import uuid

from flask import Blueprint, jsonify, request

from app.logging_setup import log_event
from app.models.db import execute
from app.services.catalog_photos import looks_like_jpeg_filename, sync_product_photo
from app.services.credentials import verify as verify_service_token
from app.services.rotation import SERVICE_NAME as CATALOG_SYNC_SERVICE_NAME

bp = Blueprint("api_catalog", __name__, url_prefix="/api/catalog")


def _require_catalog_sync_token() -> bool:
    token = request.headers.get("X-Catalog-Sync-Token", "")
    return verify_service_token(CATALOG_SYNC_SERVICE_NAME, token)


def _parse_product_payload(data):
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()
    try:
        price_cents = round(float(data.get("price", 0)) * 100)
    except (TypeError, ValueError):
        return None, "price must be a number"
    if not name or not category or not description:
        return None, "name, category, and description are required"
    if price_cents <= 0:
        return None, "price must be greater than zero"
    return {"name": name, "category": category, "description": description, "price_cents": price_cents}, None


@bp.route("/products", methods=["POST"])
def sync_product():
    request_id = uuid.uuid4().hex[:12]
    if not _require_catalog_sync_token():
        log_event(
            "service_token_auth_failed",
            request_id=request_id,
            service="catalog-sync-service",
            token=request.headers.get("X-Catalog-Sync-Token") or "(none)",
        )
        return jsonify({"error": "invalid or missing catalog-sync token"}), 401

    log_event("service_token_used", request_id=request_id, service="catalog-sync-service", action="sync_product")

    data = request.form
    product, error = _parse_product_payload(data)
    if error:
        return jsonify({"error": error}), 400

    image_path = None
    photo = request.files.get("photo")
    if photo and photo.filename:
        if not looks_like_jpeg_filename(photo.filename):
            return jsonify({"error": "photo must be a .jpg file"}), 400
        image_path = sync_product_photo(photo)
        if image_path is None:
            return jsonify({"error": "photo service unavailable"}), 502

    product_id = execute(
        "INSERT INTO products (name, category, price_cents, description, image_path) VALUES (?, ?, ?, ?, ?)",
        (product["name"], product["category"], product["price_cents"], product["description"], image_path),
    )
    log_event(
        "catalog_sync_product_created",
        product_id=product_id,
        has_photo=image_path is not None,
        request_id=request_id,
    )
    return jsonify({"product_id": product_id, "image_path": image_path, **product}), 201
