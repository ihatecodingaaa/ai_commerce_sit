"""Admin-only pages. Product management for logged-in users with
role='admin' -- a real authorization boundary (app/auth.py::require_admin_page),
not something the chatbot or any customer-facing flow can reach or grant.
Self-registration always creates role='customer' accounts
(app/routes/auth_routes.py); admin accounts only exist via database/seed.py.
"""
from flask import Blueprint, redirect, render_template, url_for

from app.auth import current_user, require_admin_page
from app.models.db import query_all

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@require_admin_page
def index():
    return redirect(url_for("admin.products"))


@bp.route("/products")
@require_admin_page
def products():
    rows = query_all(
        "SELECT id, name, category, price_cents, description, image_path FROM products ORDER BY id"
    )
    return render_template("admin_products.html", user=current_user(), products=rows)
