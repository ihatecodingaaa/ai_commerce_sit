import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.logging_setup import detect_suspicious_text, log_event
from app.models.db import execute, query_one
from app.rag.retrieval import index_content_as_kb

bp = Blueprint("api_products", __name__, url_prefix="/api")


@bp.route("/products/<int:product_id>/reviews", methods=["POST"])
@require_login
def submit_review(product_id):
    """Submit a product review.

    This is the primary attacker-controlled-content injection surface: the
    review body is stored verbatim and then auto-indexed into the knowledge
    base (visibility='public') so it becomes retrievable by
    knowledge_base_search for ANY customer session, including the
    submitter's own later chatbot conversation. See docs/attack-timeline.md
    Stage 4.
    """
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    product = query_one("SELECT id, name FROM products WHERE id = ?", (product_id,))
    if not product:
        return jsonify({"error": "product not found"}), 404

    data = request.get_json(silent=True) or request.form
    rating = int(data.get("rating", 5))
    body = str(data.get("body", "")).strip()
    if not body:
        return jsonify({"error": "review body is required"}), 400

    hits = detect_suspicious_text(body)
    if hits:
        log_event(
            "suspicious_input_pattern",
            user_id=user["id"],
            patterns=hits,
            request_id=request_id,
            source="review_submission",
        )

    review_id = execute(
        "INSERT INTO reviews (product_id, user_id, rating, body) VALUES (?, ?, ?, ?)",
        (product_id, user["id"], rating, body),
    )

    kb_id = index_content_as_kb(
        title=f"Customer review: {product['name']}",
        body=body,
        source="review",
        source_id=review_id,
        visibility="public",
    )

    log_event(
        "review_submitted",
        user_id=user["id"],
        product_id=product_id,
        review_id=review_id,
        kb_article_id=kb_id,
        request_id=request_id,
    )
    return jsonify({"review_id": review_id, "kb_article_id": kb_id}), 201
