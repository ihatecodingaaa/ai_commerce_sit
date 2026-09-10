"""Customer authentication (session-based).

Ordinary username/password login using Werkzeug's password hashing. This is
deliberately the *boring, correct* part of the lab: the interesting
vulnerabilities live in the chatbot/RAG/upload chain, not here. Endpoints
that return customer data must call require_login() and scope every query
to the logged-in user's id so the AI vulnerability isn't just "everything is
unauthenticated".
"""
from functools import wraps

from flask import abort, g, jsonify, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.db import query_one


def hash_password(raw: str) -> str:
    return generate_password_hash(raw)


def verify_password(raw: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, raw)


def current_user():
    if "user_id" not in session:
        return None
    if not hasattr(g, "_current_user"):
        g._current_user = query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    return g._current_user


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    """For JSON/API routes: 401 if not logged in, 403 if logged in but not
    an admin. There is no client-supplied "am I admin" input anywhere --
    role is read from the users row loaded off the session, same as every
    other authorization check in this app.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def require_admin_page(fn):
    """For HTML page routes: redirect to /login if not authenticated,
    403 page if authenticated but not an admin.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("auth.login"))
        if user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
