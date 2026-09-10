"""Shopping cart + checkout. Every route is scoped to the session user,
same pattern as the rest of the app -- a cart_items.id or orders row never
becomes reachable just because a caller knows its numeric id.
"""
import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_customer
from app.logging_setup import log_event
from app.models.db import db_cursor, execute, query_all, query_one

bp = Blueprint("api_cart", __name__, url_prefix="/api/cart")


@bp.route("", methods=["POST"])
@require_customer
def add_to_cart():
    user = current_user()
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id"))
        quantity = max(1, int(data.get("quantity", 1)))
    except (TypeError, ValueError):
        return jsonify({"error": "product_id and quantity are required"}), 400

    product = query_one("SELECT id FROM products WHERE id = ?", (product_id,))
    if not product:
        return jsonify({"error": "product not found"}), 404

    # Already in the cart -> add to the existing quantity instead of a
    # second row for the same product.
    execute(
        "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity",
        (user["id"], product_id, quantity),
    )
    log_event("cart_item_added", user_id=user["id"], product_id=product_id, request_id=uuid.uuid4().hex[:12])
    return jsonify({"status": "added"}), 201


@bp.route("/<int:item_id>", methods=["PUT"])
@require_customer
def update_cart_item(item_id):
    user = current_user()
    data = request.get_json(silent=True) or request.form
    try:
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"error": "quantity is required"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be at least 1"}), 400

    item = query_one("SELECT id FROM cart_items WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    if not item:
        return jsonify({"error": "cart item not found"}), 404

    execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (quantity, item_id))
    return jsonify({"status": "updated", "quantity": quantity})


@bp.route("/<int:item_id>", methods=["DELETE"])
@require_customer
def remove_cart_item(item_id):
    user = current_user()
    item = query_one("SELECT id FROM cart_items WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    if not item:
        return jsonify({"error": "cart item not found"}), 404

    execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
    return jsonify({"status": "removed"})


@bp.route("/checkout", methods=["POST"])
@require_customer
def checkout():
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    items = query_all(
        "SELECT c.product_id, c.quantity, p.price_cents FROM cart_items c "
        "JOIN products p ON p.id = c.product_id WHERE c.user_id = ?",
        (user["id"],),
    )
    if not items:
        return jsonify({"error": "your cart is empty"}), 400

    order_ids = []
    with db_cursor(commit=True) as cur:
        for item in items:
            total_cents = item["price_cents"] * item["quantity"]
            cur.execute(
                "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) "
                "VALUES (?, ?, ?, ?, 'placed')",
                (user["id"], item["product_id"], item["quantity"], total_cents),
            )
            order_ids.append(cur.lastrowid)
        cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))

    log_event("checkout_completed", user_id=user["id"], order_ids=order_ids, request_id=request_id)
    return jsonify({"status": "ok", "order_ids": order_ids}), 201
