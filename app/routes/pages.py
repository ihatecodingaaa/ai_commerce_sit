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
    # Only the two staff named in the page copy itself (see about.html) --
    # this is the storefront's one legitimate, unauthenticated source of
    # real staff names, per docs/attack-timeline.md Stage 2.
    rows = query_all(
        "SELECT name, title FROM employees WHERE name IN ('Priya Nair', 'Dana Okafor')"
    )
    staff = {row["name"]: row for row in rows}
    return render_template("about.html", user=current_user(), staff=staff)


@bp.route("/products")
def products():
    rows = query_all(
        "SELECT p.id, p.name, p.category, p.price_cents, p.description, p.image_path, "
        "COALESCE(AVG(r.rating), 0) AS avg_rating, COUNT(r.id) AS review_count "
        "FROM products p LEFT JOIN reviews r ON r.product_id = p.id "
        "GROUP BY p.id ORDER BY p.id"
    )
    category_counts = {}
    for p in rows:
        category_counts[p["category"]] = category_counts.get(p["category"], 0) + 1
    categories = [{"name": name, "count": count} for name, count in category_counts.items()]
    return render_template("products.html", user=current_user(), products=rows, categories=categories)


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
    avg_rating = sum(r["rating"] for r in reviews) / len(reviews) if reviews else 0
    return render_template(
        "product_detail.html", user=current_user(), product=product, reviews=reviews, avg_rating=avg_rating
    )


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
    (/support/tickets) so a customer chatting with the concierge and a customer
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
        "SELECT id, ticket_ref, subject, body, status, admin_reply, customer_photo_path, created_at "
        "FROM tickets WHERE user_id = ? AND visibility = 'customer' ORDER BY created_at DESC",
        (user["id"],),
    )
    return render_template("support_tickets.html", user=user, tickets=tickets)


@bp.route("/account")
def account():
    user = current_user()
    if not user:
        # Matches the reference: an unauthenticated visitor sees a
        # "sign in or create an account" prompt in place of the page,
        # not a redirect.
        return render_template("account.html", user=None, orders=[])
    orders = query_all(
        "SELECT o.id, o.quantity, o.total_cents, o.status, o.created_at, p.name AS product_name "
        "FROM orders o JOIN products p ON p.id = o.product_id "
        "WHERE o.user_id = ? ORDER BY o.created_at DESC",
        (user["id"],),
    )
    return render_template("account.html", user=user, orders=orders)
