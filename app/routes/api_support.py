import random
import uuid

from flask import Blueprint, Response, jsonify, request

from app.auth import current_user, require_login
from app.logging_setup import detect_suspicious_text, log_event
from app.models.db import execute, query_one
from app.services.image_client import fetch_screenshot, upload_screenshot

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


def _own_customer_ticket(ticket_id: int, user_id: int):
    """Ownership check mirroring app/tools/ticket_search.py's scoping
    (user_id = ? AND visibility = 'customer') -- a customer may only ever
    touch their own customer-visibility ticket, never another customer's
    or an internal one.
    """
    return query_one(
        "SELECT id FROM tickets WHERE id = ? AND user_id = ? AND visibility = 'customer'",
        (ticket_id, user_id),
    )


@bp.route("/tickets/<int:ticket_id>/screenshot", methods=["POST"])
@require_login
def upload_own_ticket_screenshot(ticket_id):
    """Legitimate customer-facing entry point into support-image-service,
    parallel to app/routes/api_admin_tickets.py's admin-only one: a
    customer attaching a photo of a defect to their own ticket is a real,
    ordinary storefront feature, not exploit-only plumbing. Same backend
    caller (app/services/image_client.py), same in-process credential --
    the only difference from the admin path is which Flask route (and
    which ownership check) is allowed to trigger it. The service itself
    still can't tell "this backend, on this customer's behalf" apart from
    anyone who has the token directly, which is exactly what Stage 6-7 of
    docs/attack-timeline.md exploits.
    """
    user = current_user()
    request_id = uuid.uuid4().hex[:12]

    if not _own_customer_ticket(ticket_id, user["id"]):
        return jsonify({"error": "ticket not found"}), 404

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "file field is required"}), 400

    image_id = upload_screenshot(file)
    if image_id is None:
        return jsonify({"error": "screenshot service unavailable"}), 502

    execute(
        "UPDATE tickets SET customer_screenshot_image_id = ? WHERE id = ?",
        (image_id, ticket_id),
    )
    log_event(
        "customer_ticket_screenshot_uploaded",
        user_id=user["id"],
        ticket_id=ticket_id,
        image_id=image_id,
        request_id=request_id,
    )
    return jsonify({"image_id": image_id}), 201


@bp.route("/tickets/<int:ticket_id>/screenshot", methods=["GET"])
@require_login
def get_own_ticket_screenshot(ticket_id):
    user = current_user()
    ticket = _own_customer_ticket(ticket_id, user["id"])
    if not ticket:
        return jsonify({"error": "ticket not found"}), 404

    row = query_one(
        "SELECT customer_screenshot_image_id FROM tickets WHERE id = ?", (ticket_id,)
    )
    if not row or not row["customer_screenshot_image_id"]:
        return jsonify({"error": "no screenshot for this ticket"}), 404

    result = fetch_screenshot(row["customer_screenshot_image_id"])
    if result is None:
        return jsonify({"error": "screenshot service unavailable"}), 502

    data, content_type = result
    return Response(data, mimetype=content_type)
