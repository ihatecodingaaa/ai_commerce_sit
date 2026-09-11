"""Admin support-ticket management. require_admin-gated, same as product
management -- a customer session, no matter whose, never reaches this.

Screenshot attachments (POST/GET .../screenshot) are the legitimate,
admin-only entry point into the support-image-service upload pipeline --
see app/services/image_client.py for how this backend calls that internal
service on the admin's behalf. GET .../customer-screenshot is the
read-only counterpart for viewing what a customer attached to their own
ticket via app/routes/api_support.py -- two independent, legitimate
features sharing the same internal image service and token.
"""
import uuid

from flask import Blueprint, Response, jsonify, request

from app.auth import current_user, require_admin
from app.logging_setup import log_event
from app.models.db import execute, query_one
from app.services.image_client import fetch_screenshot, upload_screenshot

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


@bp.route("/<int:ticket_id>/screenshot", methods=["POST"])
@require_admin
def upload_ticket_screenshot(ticket_id):
    admin = current_user()
    request_id = uuid.uuid4().hex[:12]

    ticket = query_one(
        "SELECT id FROM tickets WHERE id = ? AND visibility = 'customer'", (ticket_id,)
    )
    if not ticket:
        return jsonify({"error": "ticket not found"}), 404

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "file field is required"}), 400

    image_id = upload_screenshot(file)
    if image_id is None:
        return jsonify({"error": "screenshot service unavailable"}), 502

    execute("UPDATE tickets SET screenshot_image_id = ? WHERE id = ?", (image_id, ticket_id))
    log_event(
        "admin_ticket_screenshot_uploaded",
        admin_id=admin["id"],
        ticket_id=ticket_id,
        image_id=image_id,
        request_id=request_id,
    )
    return jsonify({"image_id": image_id}), 201


@bp.route("/<int:ticket_id>/screenshot", methods=["GET"])
@require_admin
def get_ticket_screenshot(ticket_id):
    ticket = query_one(
        "SELECT screenshot_image_id FROM tickets WHERE id = ? AND visibility = 'customer'",
        (ticket_id,),
    )
    if not ticket or not ticket["screenshot_image_id"]:
        return jsonify({"error": "no screenshot for this ticket"}), 404

    result = fetch_screenshot(ticket["screenshot_image_id"])
    if result is None:
        return jsonify({"error": "screenshot service unavailable"}), 502

    data, content_type = result
    return Response(data, mimetype=content_type)


@bp.route("/<int:ticket_id>/customer-screenshot", methods=["GET"])
@require_admin
def get_customer_ticket_screenshot(ticket_id):
    """Read-only: lets an admin see the photo a customer attached to their
    own ticket (app/routes/api_support.py::upload_own_ticket_screenshot).
    No ownership check needed here -- an admin, unlike a customer, is
    allowed to view any customer-visibility ticket."""
    ticket = query_one(
        "SELECT customer_screenshot_image_id FROM tickets WHERE id = ? AND visibility = 'customer'",
        (ticket_id,),
    )
    if not ticket or not ticket["customer_screenshot_image_id"]:
        return jsonify({"error": "no screenshot for this ticket"}), 404

    result = fetch_screenshot(ticket["customer_screenshot_image_id"])
    if result is None:
        return jsonify({"error": "screenshot service unavailable"}), 502

    data, content_type = result
    return Response(data, mimetype=content_type)
