import uuid

from flask import Blueprint, jsonify, request

from app.auth import current_user, require_login
from app.chatbot.agent import (
    get_visible_history,
    handle_chat_message,
    reset_all_conversations,
    reset_conversation,
)

bp = Blueprint("api_chat", __name__, url_prefix="/api")


@bp.route("/chat/history", methods=["GET"])
@require_login
def chat_history():
    """Returns the logged-in customer's own conversation so the chat widget
    can re-render it after a page navigation. Conversation state already
    lives server-side per user_id (app/chatbot/agent.py) -- this just reads
    it back, scoped to the calling session the same way every other
    customer-data endpoint is.
    """
    user = current_user()
    return jsonify({"messages": get_visible_history(user["id"])})


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


@bp.route("/internal/chat/reset-all", methods=["POST"])
def chat_reset_all():
    """Wipe in-memory chat history for every user. No login check -- this
    is meant for scripts/reset_lab.sh (running inside the same container/
    host network namespace), not for end users, so it's restricted to
    loopback callers instead of a session.
    """
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"error": "forbidden"}), 403
    reset_all_conversations()
    return jsonify({"status": "reset"})
