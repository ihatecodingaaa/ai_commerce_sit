import random
import uuid

from flask import Blueprint, jsonify, request, send_from_directory

from app.auth import current_user, require_login
from app.config import config
from app.logging_setup import detect_suspicious_text, log_event
from app.models.db import execute, query_one
from app.services.ticket_photos import save_ticket_photo

bp = Blueprint("api_support", __name__, url_prefix="/api")


@bp.route("/tickets", methods=["POST"])
@require_login
def create_ticket():
    user = current_user()
    request_id = uuid.uuid4().hex[:12]
    data = request.get_json(silent=True) or request.form
    subject = str(data.get("subject", "")).strip()
    body = str(data.get("body", "")).strip()
    if not subject or not body:
        return jsonify({"error": "subject and body are required"}), 400

    hits = detect_suspicious_text(body)
    if hits:
        log_event(
            "suspicious_input_pattern",
            user_id=user["id"],
            patterns=hits,
            request_id=request_id,
            source="ticket_submission",
        )

    ticket_ref = f"CUST-{random.randint(10000, 99999)}"
    execute(
        "INSERT INTO tickets (ticket_ref, user_id, subject, body, status, visibility) "
        "VALUES (?, ?, ?, ?, 'open', 'customer')",
        (ticket_ref, user["id"], subject, body),
    )
    log_event("ticket_created", user_id=user["id"], ticket_ref=ticket_ref, request_id=request_id)
    return jsonify({"ticket_ref": ticket_ref, "status": "open"}), 201


@bp.route("/tickets/<int:ticket_id>/photo", methods=["POST"])
@require_login
def upload_ticket_photo(ticket_id):
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    # Scoped to the caller's own ticket -- a customer session, no matter
    # whose, never reaches another customer's ticket here.
    ticket = query_one(
        "SELECT id FROM tickets WHERE id = ? AND user_id = ? AND visibility = 'customer'",
        (ticket_id, user["id"]),
    )
    if not ticket:
        return jsonify({"error": "ticket not found"}), 404

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "file field is required"}), 400

    try:
        filename = save_ticket_photo(file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    execute("UPDATE tickets SET customer_photo_path = ? WHERE id = ?", (filename, ticket_id))
    log_event("ticket_photo_uploaded", user_id=user["id"], ticket_id=ticket_id, request_id=request_id)
    return jsonify({"status": "uploaded"}), 201


@bp.route("/tickets/<int:ticket_id>/photo", methods=["GET"])
@require_login
def get_ticket_photo(ticket_id):
    user = current_user()
    ticket = query_one(
        "SELECT customer_photo_path FROM tickets WHERE id = ? AND user_id = ? AND visibility = 'customer'",
        (ticket_id, user["id"]),
    )
    if not ticket or not ticket["customer_photo_path"]:
        return jsonify({"error": "no photo for this ticket"}), 404
    return send_from_directory(config.TICKET_PHOTO_DIR, ticket["customer_photo_path"])
