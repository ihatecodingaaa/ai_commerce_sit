"""Admin-only pages: product management and support-ticket handling, for
logged-in users with role='admin' -- a real authorization boundary
(app/auth.py::require_admin_page), not something the chatbot or any
customer-facing flow can reach or grant. Self-registration always creates
role='customer' accounts (app/routes/auth_routes.py); admin accounts only
exist via database/seed.py.
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


@bp.route("/tickets")
@require_admin_page
def tickets():
    """All customer-visibility tickets across every customer -- explicitly
    NOT the same query as the customer-scoped one in pages.py::support_tickets,
    which filters to `WHERE user_id = ?`. Internal (visibility='internal')
    tickets are still excluded here; this is staff tooling for customer
    support, not a window into the internal engineering tickets that are
    the lab's own vulnerability target.
    """
    rows = query_all(
        "SELECT t.id, t.ticket_ref, t.subject, t.body, t.status, t.admin_reply, t.created_at, "
        "u.username, u.full_name FROM tickets t JOIN users u ON u.id = t.user_id "
        "WHERE t.visibility = 'customer' ORDER BY t.created_at DESC"
    )
    return render_template("admin_tickets.html", user=current_user(), tickets=rows)
