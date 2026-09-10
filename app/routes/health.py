from flask import Blueprint, jsonify

from app.chatbot.ollama_client import is_reachable
from app.models.db import query_one

bp = Blueprint("health", __name__)


@bp.route("/health")
def health():
    db_ok = True
    try:
        query_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False

    ollama_ok = is_reachable()

    status = "ok" if (db_ok and ollama_ok) else "degraded"
    return jsonify(
        {
            "status": status,
            "app": "up",
            "database": "up" if db_ok else "down",
            "ollama": "up" if ollama_ok else "down",
        }
    ), (200 if status == "ok" else 503)
