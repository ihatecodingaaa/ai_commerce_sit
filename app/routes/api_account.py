"""Self-service account editing. Every customer/admin can edit their own
profile (full name, email, preset avatar, password) -- always scoped to
`session['user_id']`, same pattern as every other customer-data endpoint
in this app. There is no field anywhere in this request that lets a caller
target a different account, and role is never accepted from the client
(see app/routes/auth_routes.py and database/seed.py for how role gets
set -- never here).
"""
import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, hash_password, require_login, verify_password
from app.avatars import is_valid_avatar
from app.logging_setup import log_event
from app.models.db import execute, query_one

bp = Blueprint("api_account", __name__, url_prefix="/api/account")


@bp.route("", methods=["PUT"])
@require_login
def update_account():
    user = current_user()
    request_id = uuid.uuid4().hex[:12]
    data = request.get_json(silent=True) or request.form

    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    avatar = str(data.get("avatar", user["avatar"])).strip()

    if not full_name or not email:
        return jsonify({"error": "full name and email are required"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "enter a valid email address"}), 400
    if not is_valid_avatar(avatar):
        return jsonify({"error": "not a recognized preset avatar"}), 400

    clash = query_one("SELECT id FROM users WHERE email = ? AND id != ?", (email, user["id"]))
    if clash:
        return jsonify({"error": "that email is already in use"}), 400

    new_password = data.get("new_password") or ""
    if new_password:
        current_password = data.get("current_password") or ""
        if not verify_password(current_password, user["password_hash"]):
            return jsonify({"error": "current password is incorrect"}), 400
        if len(new_password) < 8:
            return jsonify({"error": "new password must be at least 8 characters"}), 400
        execute(
            "UPDATE users SET full_name = ?, email = ?, avatar = ?, password_hash = ? WHERE id = ?",
            (full_name, email, avatar, hash_password(new_password), user["id"]),
        )
        log_event("account_password_changed", user_id=user["id"], request_id=request_id)
    else:
        execute(
            "UPDATE users SET full_name = ?, email = ?, avatar = ? WHERE id = ?",
            (full_name, email, avatar, user["id"]),
        )

    log_event("account_updated", user_id=user["id"], request_id=request_id)
    return jsonify({"full_name": full_name, "email": email, "avatar": avatar})
