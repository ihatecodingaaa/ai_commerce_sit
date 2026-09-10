"""Admin support-ticket management. require_admin-gated, same as product
management -- a customer session, no matter whose, never reaches this.
"""
import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_admin
from app.logging_setup import log_event
from app.models.db import execute, query_one

bp = Blueprint("api_admin_tickets", __name__, url_prefix="/api/admin/tickets")

VALID_STATUSES = {"open", "in_progress", "resolved"}


@bp.route("/<int:ticket_id>", methods=["PUT"])
@require_admin
def update_ticket(ticket_id):
    admin = current_user()
    request_id = uuid.uuid4().hex[:12]

    ticket = query_one(
        "SELECT id FROM tickets WHERE id = ? AND visibility = 'customer'", (ticket_id,)
    )
    if not ticket:
        return jsonify({"error": "ticket not found"}), 404

    data = request.get_json(silent=True) or request.form
    status = str(data.get("status", "")).strip()
    reply = data.get("admin_reply")

    if status and status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(VALID_STATUSES)}"}), 400

    if status:
        execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
    if reply is not None:
        execute("UPDATE tickets SET admin_reply = ? WHERE id = ?", (str(reply).strip() or None, ticket_id))

    log_event(
        "admin_ticket_updated",
        admin_id=admin["id"],
        ticket_id=ticket_id,
        status=status or None,
        replied=reply is not None,
        request_id=request_id,
    )
    return jsonify({"status": "updated"})
