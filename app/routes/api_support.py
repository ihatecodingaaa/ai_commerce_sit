import random
import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.logging_setup import detect_suspicious_text, log_event
from app.models.db import execute

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
