"""Admin product management API. Every route requires role='admin'
(app/auth.py::require_admin) -- a real, server-side-enforced authorization
boundary, unrelated to and unreachable from the chatbot/tool-calling flow.
"""
import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_admin
from app.logging_setup import log_event
from app.models.db import db_cursor, execute, query_one

bp = Blueprint("api_admin", __name__, url_prefix="/api/admin")


def _parse_product_payload(data):
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()
    try:
        # round(), not int(): float multiplication (e.g. 19.99 * 100) can
        # land a hair under the intended integer (1998.9999999999998),
        # which int() would silently truncate to the wrong cent value.
        price_cents = round(float(data.get("price", 0)) * 100)
    except (TypeError, ValueError):
        return None, "price must be a number"
    if not name or not category or not description:
        return None, "name, category, and description are required"
    if price_cents <= 0:
        return None, "price must be greater than zero"
    return {"name": name, "category": category, "description": description, "price_cents": price_cents}, None


@bp.route("/products", methods=["POST"])
@require_admin
def create_product():
    user = current_user()
    request_id = uuid.uuid4().hex[:12]
    data = request.get_json(silent=True) or request.form

    product, error = _parse_product_payload(data)
    if error:
        return jsonify({"error": error}), 400

    product_id = execute(
        "INSERT INTO products (name, category, price_cents, description) VALUES (?, ?, ?, ?)",
        (product["name"], product["category"], product["price_cents"], product["description"]),
    )
    log_event("admin_product_created", admin_id=user["id"], product_id=product_id, request_id=request_id)
    return jsonify({"product_id": product_id, **product}), 201


@bp.route("/products/<int:product_id>", methods=["PUT"])
@require_admin
def update_product(product_id):
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    existing = query_one("SELECT id FROM products WHERE id = ?", (product_id,))
    if not existing:
        return jsonify({"error": "product not found"}), 404

    data = request.get_json(silent=True) or request.form
    product, error = _parse_product_payload(data)
    if error:
        return jsonify({"error": error}), 400

    execute(
        "UPDATE products SET name = ?, category = ?, price_cents = ?, description = ? WHERE id = ?",
        (product["name"], product["category"], product["price_cents"], product["description"], product_id),
    )
    log_event("admin_product_updated", admin_id=user["id"], product_id=product_id, request_id=request_id)
    return jsonify({"product_id": product_id, **product})


@bp.route("/products/<int:product_id>", methods=["DELETE"])
@require_admin
def delete_product(product_id):
    """Hard-deletes a product and everything that references it (reviews,
    their mirrored KB articles, and orders). This is intentionally
    destructive admin power for a demo storefront -- a real production
    system would soft-delete/deactivate a product with order history
    instead of cascading a hard delete through the order ledger.
    """
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    existing = query_one("SELECT id FROM products WHERE id = ?", (product_id,))
    if not existing:
        return jsonify({"error": "product not found"}), 404

    # One transaction (one connection/cursor) so this is atomic -- a
    # second connection (e.g. the standalone delete_kb_content() helper)
    # would deadlock against this uncommitted transaction under SQLite's
    # single-writer model.
    with db_cursor(commit=True) as cur:
        review_ids = [
            row["id"]
            for row in cur.execute("SELECT id FROM reviews WHERE product_id = ?", (product_id,)).fetchall()
        ]
        for review_id in review_ids:
            cur.execute(
                "DELETE FROM kb_articles WHERE source = 'review' AND source_id = ?", (review_id,)
            )
        cur.execute("DELETE FROM reviews WHERE product_id = ?", (product_id,))
        cur.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))

    log_event(
        "admin_product_deleted",
        admin_id=user["id"],
        product_id=product_id,
        cascaded_reviews=len(review_ids),
        request_id=request_id,
    )
    return jsonify({"status": "deleted", "product_id": product_id})
