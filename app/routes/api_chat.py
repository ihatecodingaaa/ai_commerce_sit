import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.chatbot.agent import handle_chat_message, reset_conversation

bp = Blueprint("api_chat", __name__, url_prefix="/api")


@bp.route("/chat", methods=["POST"])
@require_login
def chat_endpoint():
    user = current_user()
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > 2000:
        return jsonify({"error": "message too long"}), 400

    request_id = uuid.uuid4().hex[:12]
    reply = handle_chat_message(user, message, request_id)
    return jsonify({"reply": reply, "request_id": request_id})


@bp.route("/chat/reset", methods=["POST"])
@require_login
def chat_reset():
    user = current_user()
    reset_conversation(user["id"])
    return jsonify({"status": "reset"})
