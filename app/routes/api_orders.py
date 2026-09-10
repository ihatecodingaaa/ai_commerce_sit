import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.logging_setup import log_event
from app.models.db import execute, query_one

bp = Blueprint("api_orders", __name__, url_prefix="/api")


@bp.route("/orders", methods=["POST"])
@require_login
def place_order():
    user = current_user()
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id"))
        quantity = max(1, int(data.get("quantity", 1)))
    except (TypeError, ValueError):
        return jsonify({"error": "product_id and quantity are required"}), 400

    product = query_one("SELECT id, price_cents FROM products WHERE id = ?", (product_id,))
    if not product:
        return jsonify({"error": "product not found"}), 404

    total_cents = product["price_cents"] * quantity
    order_id = execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, ?, ?, 'placed')",
        (user["id"], product_id, quantity, total_cents),
    )
    log_event(
        "order_placed",
        user_id=user["id"],
        order_id=order_id,
        product_id=product_id,
        request_id=uuid.uuid4().hex[:12],
    )
    return jsonify({"order_id": order_id, "status": "placed", "total_cents": total_cents}), 201
