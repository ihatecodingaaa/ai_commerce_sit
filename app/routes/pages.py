from flask import Blueprint, abort, redirect, render_template, send_from_directory, url_for

from app.auth import current_user
from app.config import config
from app.models.db import query_all, query_one

bp = Blueprint("pages", __name__)


@bp.route("/")
def index():
    return redirect(url_for("pages.products"))


@bp.route("/product-photos/<filename>")
def product_photo(filename):
    """Serves admin-uploaded product photos. Public/unauthenticated on
    purpose -- these are storefront images, same trust level as any other
    product page content. Filenames are always server-generated
    (uuid4 + sniffed extension, see app/services/product_photos.py), and
    send_from_directory itself rejects path traversal regardless.
    """
    return send_from_directory(config.PRODUCT_PHOTO_DIR, filename)


@bp.route("/about")
def about():
    employees = query_all("SELECT name, title, department, photo FROM employees ORDER BY id")
    return render_template("about.html", user=current_user(), employees=employees)


@bp.route("/products")
def products():
    rows = query_all(
        "SELECT id, name, category, price_cents, description, image_path FROM products ORDER BY id"
    )
    return render_template("products.html", user=current_user(), products=rows)


@bp.route("/products/<int:product_id>")
def product_detail(product_id):
    product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not product:
        abort(404)
    reviews = query_all(
        "SELECT r.id, r.rating, r.body, r.created_at, r.user_id, u.username, u.avatar FROM reviews r "
        "JOIN users u ON u.id = r.user_id WHERE r.product_id = ? ORDER BY r.created_at DESC",
        (product_id,),
    )
    return render_template("product_detail.html", user=current_user(), product=product, reviews=reviews)


@bp.route("/cart")
def cart():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))
    if user["role"] != "customer":
        # Admin is a staff role, not a shopper -- it has no cart to view.
        abort(403)
    rows = query_all(
        "SELECT c.id, c.quantity, c.product_id, p.name AS product_name, p.price_cents, p.image_path "
        "FROM cart_items c JOIN products p ON p.id = c.product_id "
        "WHERE c.user_id = ? ORDER BY c.created_at DESC",
        (user["id"],),
    )
    return render_template("cart.html", user=user, cart_items=rows)


@bp.route("/support")
def support():
    """The chat-only support page. Split from ticket submission
    (/support/tickets) so a customer chatting with Shopilot and a customer
    filling out a ticket form are never fighting for the same page layout
    -- and so neither flow gets tangled up with the other's state.
    """
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("support.html", user=user)


@bp.route("/support/tickets")
def support_tickets():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))
    tickets = query_all(
        "SELECT ticket_ref, subject, body, status, admin_reply, created_at FROM tickets "
        "WHERE user_id = ? AND visibility = 'customer' ORDER BY created_at DESC",
        (user["id"],),
    )
    return render_template("support_tickets.html", user=user, tickets=tickets)


@bp.route("/account")
def account():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))
    orders = query_all(
        "SELECT o.id, o.quantity, o.total_cents, o.status, o.created_at, p.name AS product_name "
        "FROM orders o JOIN products p ON p.id = o.product_id "
        "WHERE o.user_id = ? ORDER BY o.created_at DESC",
        (user["id"],),
    )
    return render_template("account.html", user=user, orders=orders)
