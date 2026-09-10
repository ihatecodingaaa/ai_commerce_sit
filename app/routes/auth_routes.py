import uuid

from flask import Blueprint, redirect, render_template, request, session, url_for

from app.auth import current_user, hash_password, verify_password
from app.logging_setup import log_event
from app.models.db import execute, query_one

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", user=current_user())

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password or not full_name:
        return render_template("register.html", user=None, error="All fields are required."), 400

    if query_one("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)):
        return render_template("register.html", user=None, error="Username or email already registered."), 400

    user_id = execute(
        "INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'customer')",
        (username, email, hash_password(password), full_name),
    )
    session["user_id"] = user_id
    log_event("user_registered", user_id=user_id, username=username, request_id=uuid.uuid4().hex[:12])
    return redirect(url_for("pages.account"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", user=current_user())

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    request_id = uuid.uuid4().hex[:12]

    user = query_one("SELECT * FROM users WHERE username = ?", (username,))
    if not user or not verify_password(password, user["password_hash"]):
        log_event("login_failed", username=username, request_id=request_id)
        return render_template("login.html", user=None, error="Invalid username or password."), 401

    session["user_id"] = user["id"]
    log_event("login_success", user_id=user["id"], username=username, request_id=request_id)
    return redirect(url_for("pages.account"))


@bp.route("/logout", methods=["POST"])
def logout():
    user = current_user()
    if user:
        log_event("logout", user_id=user["id"], request_id=uuid.uuid4().hex[:12])
    session.clear()
    return redirect(url_for("pages.index"))
