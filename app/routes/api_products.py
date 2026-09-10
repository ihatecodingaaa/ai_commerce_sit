import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.logging_setup import detect_suspicious_text, log_event
from app.models.db import execute, query_one
from app.rag.retrieval import delete_kb_content, index_content_as_kb, update_kb_content

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


@bp.route("/reviews/<int:review_id>", methods=["PUT"])
@require_login
def update_review(review_id):
    """Edit one of the logged-in customer's own reviews. Ownership is
    enforced server-side (WHERE user_id = ?) -- same pattern as every other
    customer-scoped endpoint in this app; a review_id belonging to another
    customer is rejected regardless of what the client sends.

    The mirrored KB article is updated too, so an edited review's new text
    is what the chatbot's knowledge_base_search will retrieve from then on
    -- the injection surface stays live for edited content, not just the
    original submission.
    """
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    review = query_one(
        "SELECT id, user_id, product_id FROM reviews WHERE id = ?", (review_id,)
    )
    if not review or review["user_id"] != user["id"]:
        return jsonify({"error": "review not found"}), 404

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
            source="review_edit",
        )

    execute("UPDATE reviews SET rating = ?, body = ? WHERE id = ?", (rating, body, review_id))
    update_kb_content(source="review", source_id=review_id, body=body)

    log_event("review_updated", user_id=user["id"], review_id=review_id, request_id=request_id)
    return jsonify({"review_id": review_id, "status": "updated"})


@bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@require_login
def delete_review(review_id):
    """Delete one of the logged-in customer's own reviews, and the KB
    article that mirrored it -- deleting a review also removes it from
    what the chatbot can retrieve.
    """
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    review = query_one("SELECT id, user_id FROM reviews WHERE id = ?", (review_id,))
    if not review or review["user_id"] != user["id"]:
        return jsonify({"error": "review not found"}), 404

    execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    delete_kb_content(source="review", source_id=review_id)

    log_event("review_deleted", user_id=user["id"], review_id=review_id, request_id=request_id)
    return jsonify({"status": "deleted"})
