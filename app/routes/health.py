from flask import Blueprint, jsonify

from app.chatbot.ollama_client import fallback_active, is_ollama_reachable, is_reachable
from app.config import config
from app.models.db import query_one

bp = Blueprint("health", __name__)


@bp.route("/health")
def health():
    db_ok = True
    try:
        query_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False

    primary_ok = is_reachable()

    body = {
        "app": "up",
        "database": "up" if db_ok else "down",
        "llm_backend": config.LLM_BACKEND,
        "llm_primary": "up" if primary_ok else "down",
    }

    # The chatbot is still servable off local Ollama even when the hosted
    # backend is down -- report that explicitly instead of only the
    # primary's status, so "degraded" doesn't wrongly suggest the chatbot
    # itself is unusable. See app/chatbot/ollama_client.py's chat().
    chatbot_ok = primary_ok
    if config.LLM_BACKEND == "openai" and config.LLM_FALLBACK_TO_OLLAMA:
        ollama_ok = is_ollama_reachable()
        body["llm_fallback_ollama"] = "up" if ollama_ok else "down"
        body["llm_fallback_active"] = fallback_active()
        chatbot_ok = primary_ok or ollama_ok

    status = "ok" if (db_ok and chatbot_ok) else "degraded"
    body["status"] = status
    return jsonify(body), (200 if status == "ok" else 503)
