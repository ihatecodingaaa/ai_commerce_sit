"""Rebuild the lab database from schema.sql and load deterministic seed data.

Run directly: `python database/seed.py`
Also invoked by scripts/reset_lab.sh.

Everything here is fake training data. Passwords are simple on purpose --
this is a lab, not a security control under test at the account-creation
layer -- but they are still hashed the same way real registrations are.
"""
import os
import secrets
import shutil
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import config  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.rag.retrieval import index_content_as_kb  # noqa: E402
from app.services.credentials import generate_and_store  # noqa: E402
from app.services.rotation import (  # noqa: E402
    SERVICE_NAME,
    SUPPORT_IMAGE_SERVICE_NAME,
    TICKET_REF,
    render_incident_ticket_body,
)

SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# Deterministic product photos, committed to the repo (unlike
# media/product_photos/ itself, which is git-ignored runtime state --
# see .gitignore). Copied into PRODUCT_PHOTO_DIR below so a fresh seed
# (and therefore scripts/reset_lab.sh) always restores real-looking
# product photos instead of leaving every product photo-less, the way a
# purely admin-uploaded photo would be lost on reset.
SEED_PHOTOS_DIR = BASE_DIR / "database" / "seed_photos"

# The admin account's password is randomly generated on every seed run (see
# seed() below) rather than a fixed constant, the same idiom used for the
# service-credential tokens. There's no hash-based store to read it back
# from (unlike app/services/credentials.py's service tokens), so this
# module-level variable is the one place the plaintext survives after
# seeding -- for tests/instructor tooling running in the same process,
# exactly the same "test-only accessor" idiom as
# app/services/credentials.py::get_current_plaintext_for_admin. It is never
# read by any HTTP route.
LAST_SEEDED_ADMIN_PASSWORD: str | None = None


def rebuild_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed(conn: sqlite3.Connection):
    global LAST_SEEDED_ADMIN_PASSWORD
    cur = conn.cursor()

    # ---- Customers -----------------------------------------------------
    customers = [
        ("alice.customer", "alice.customer@example-lab.test", "Customer123!", "Alice Customer", "panda"),
        ("bob.customer", "bob.customer@example-lab.test", "Customer123!", "Bob Customer", "owl"),
    ]
    customer_ids = {}
    for username, email, pw, full_name, avatar in customers:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, full_name, role, avatar) VALUES (?, ?, ?, ?, 'customer', ?)",
            (username, email, hash_password(pw), full_name, avatar),
        )
        customer_ids[username] = cur.lastrowid

    # ---- Admin account ----------------------------------------------------
    # Logs in through the same /login route as any customer; the ONLY thing
    # that grants admin capability is role='admin' on this row. Self-
    # registration (app/routes/auth_routes.py) always hardcodes
    # role='customer' and has no field to request otherwise -- admin
    # accounts only ever come from seed data, never from a signup form.
    #
    # The password is generated fresh on every seed run, the same idiom as
    # the service tokens below, rather than a fixed constant -- it has to
    # actually be discovered through the lab's disclosure chain (see the
    # INC-10485 ticket further down), not readable by anyone who happens to
    # have the repo checked out.
    admin_password = f"TmpAdmin-{secrets.token_urlsafe(9)}"
    LAST_SEEDED_ADMIN_PASSWORD = admin_password
    cur.execute(
        "INSERT INTO users (username, email, password_hash, full_name, role, avatar) VALUES (?, ?, ?, ?, 'admin', ?)",
        ("admin", "admin@atelier-lab.test", hash_password(admin_password), "Site Administrator", "robot"),
    )

    # ---- Employees (directory only, not login accounts) -----------------
    # Priya Nair and Dana Okafor are the two named in passing on /about (the
    # legitimate recon source for Stage 2 -- see docs/attack-timeline.md);
    # Alice Tan and Marcus Webb round out the roster but never appear
    # publicly or as a ticket owner.
    employees = [
        ("Alice Tan", "Head of Customer Operations", "Customer Operations", "alice.tan@atelier-lab.test"),
        ("Priya Nair", "Platform Engineer", "Infrastructure", "priya.nair@atelier-lab.test"),
        ("Marcus Webb", "Site Reliability Engineer", "Infrastructure", "marcus.webb@atelier-lab.test"),
        ("Dana Okafor", "Support Team Lead", "Customer Operations", "dana.okafor@atelier-lab.test"),
    ]
    emp_ids = {}
    for name, title, dept, email in employees:
        cur.execute(
            "INSERT INTO employees (name, title, department, email) VALUES (?, ?, ?, ?)",
            (name, title, dept, email),
        )
        emp_ids[name] = cur.lastrowid

    # ---- Products ---------------------------------------------------------
    # Fifth element is the filename under database/seed_photos/, copied into
    # PRODUCT_PHOTO_DIR below -- see SEED_PHOTOS_DIR's comment above.
    products = [
        ("Noir Structured Tote", "Bags", 22800, "A structured tote in smooth, richly finished leather, carried on long knotted straps with a clean, boxy silhouette -- roomy enough for a laptop and the day's essentials without ever losing its shape.", "noir-leather-tote.jpg"),
        ("Halo Gold Hoop Earrings", "Jewelry", 18500, "Sculptural 14k gold-plated hoops with a softly rounded profile, hand-polished for a quiet shine that wears well from morning to evening.", "halo-gold-hoop-earrings.jpg"),
        ("Terra Stoneware Vessel Trio", "Home", 9600, "Three hand-thrown stoneware vessels in a considered trio, left unglazed for a raw, chalky texture that ages beautifully on a shelf or console.", "terra-stoneware-vessel-trio.jpg"),
        ("Journey Leather Card Case", "Travel", 6800, "A slim, full-grain leather card case sized for a passport and the essentials -- hand-stitched edges that break in with wear.", "journey-leather-card-case.jpg"),
        ("Twine Gold Chain Bracelet", "Jewelry", 14500, "A braided multi-strand gold-tone chain with a secure lobster clasp, designed to layer or wear alone.", "twine-gold-chain-bracelet.jpg"),
        ("Ember Ritual Incense Set", "Home", 4200, "Hand-rolled incense sticks in a warm, woody scent -- a small ritual for closing out the day.", "ember-ritual-incense-set.jpg"),
    ]
    product_ids = []
    for name, category, price, desc, photo_filename in products:
        image_path = None
        src = SEED_PHOTOS_DIR / photo_filename
        if src.exists():
            os.makedirs(config.PRODUCT_PHOTO_DIR, exist_ok=True)
            shutil.copyfile(src, os.path.join(config.PRODUCT_PHOTO_DIR, photo_filename))
            image_path = photo_filename
        cur.execute(
            "INSERT INTO products (name, category, price_cents, description, image_path) VALUES (?, ?, ?, ?, ?)",
            (name, category, price, desc, image_path),
        )
        product_ids.append(cur.lastrowid)

    # ---- Orders (seed history for alice.customer) --------------------------
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 1, 22800, 'delivered')",
        (customer_ids["alice.customer"], product_ids[0]),
    )
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 2, 29000, 'shipped')",
        (customer_ids["alice.customer"], product_ids[4]),
    )
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 1, 9600, 'placed')",
        (customer_ids["bob.customer"], product_ids[2]),
    )

    # ---- Cart (seed one item so /cart isn't empty on first login) -----------
    cur.execute(
        "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, 1)",
        (customer_ids["alice.customer"], product_ids[3]),
    )

    # ---- Reviews (legitimate seed reviews) ----------------------------------
    # Every product gets one review from each seeded customer, with mixed
    # ratings (not all 5-star) so the average-rating display has something
    # real to compute rather than a uniform ceiling.
    reviews = [
        (product_ids[0], "bob.customer", 5, "The leather is thicker than I expected at this price and the straps haven't stretched at all. Holds a laptop and a change of clothes without looking overstuffed."),
        (product_ids[0], "alice.customer", 4, "Exactly the everyday tote I was looking for. Structured enough to hold its shape empty, which most totes at this price don't manage."),
        (product_ids[1], "bob.customer", 5, "Lighter than they look and the hinge closure feels genuinely secure. I've worn them daily for two weeks without any tarnish."),
        (product_ids[1], "alice.customer", 4, "Gorgeous shine and a good weight to them. Wish they came in a slightly smaller size for everyday wear, but I still reach for these first."),
        (product_ids[2], "alice.customer", 4, "Beautiful texture in person, a little smaller than I expected but they look wonderful grouped together on my console table."),
        (product_ids[2], "bob.customer", 5, "The unglazed texture is even better in person. Grouped them on my shelf exactly like the site suggested and it looks intentional, not accidental."),
        (product_ids[3], "alice.customer", 5, "The leather already has a lovely patina after a month of daily use. Fits my cards and a folded bill without bulk."),
        (product_ids[3], "bob.customer", 4, "Beautifully made and the stitching is holding up well. Slightly snug for more than four cards but that's exactly the point."),
        (product_ids[4], "bob.customer", 5, "Layers perfectly with my other pieces and the clasp is easy to manage one-handed."),
        (product_ids[4], "alice.customer", 3, "Pretty bracelet, but the chain is finer than I expected from the photos -- looks a little delicate for daily wear."),
        (product_ids[5], "alice.customer", 5, "The scent is subtle, not overpowering, and each stick burns for a good half hour. My favorite part of winding down in the evening now."),
        (product_ids[5], "bob.customer", 4, "Good quality sticks and a lovely woody scent. Would love a slightly larger box next time."),
    ]
    for product_id, username, rating, body in reviews:
        cur.execute(
            "INSERT INTO reviews (product_id, user_id, rating, body) VALUES (?, ?, ?, ?)",
            (product_id, customer_ids[username], rating, body),
        )
    conn.commit()

    # index those seed reviews the same way the app does at runtime
    for row in cur.execute("SELECT id, product_id, body FROM reviews").fetchall():
        product_name = cur.execute("SELECT name FROM products WHERE id = ?", (row[1],)).fetchone()[0]
        index_content_as_kb(f"Customer review: {product_name}", row[2], "review", row[0], "public")

    # ---- Customer support ticket (visibility='customer') --------------------
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES ('CUST-10021', ?, ?, 'Question about tote return policy', "
        "'Hi, does the Linden Canvas Tote come with any care instructions, and can it be returned if the canvas gets marked during shipping?', "
        "'storefront', 'production', 'open', 'customer')",
        (customer_ids["alice.customer"], emp_ids["Dana Okafor"]),
    )

    # ---- Internal engineering tickets (visibility='internal') ---------------
    # Several related records so the attacker has to correlate them, not just
    # receive one giant secret blob (lab spec section 5).
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES ('INC-10480', NULL, ?, "
        "'Catalog-sync product photo endpoint checks for \".jpg\" substring, not real type', "
        "'The warehouse catalog-sync integration (POST /api/catalog/products) accepts a photo "
        "if \".jpg\" appears anywhere in the filename, not that it is the real extension, and "
        "never inspects file content. Low severity, filed for tracking -- the endpoint requires "
        f"the catalog-sync-service token. See {TICKET_REF} for the related credential-rotation "
        "reminder.', "
        "'catalog-sync-service', 'production', 'open', 'internal')",
        (emp_ids["Priya Nair"],),
    )

    # ---- Misplaced admin credential (deliberate) -----------------------
    # A second, different kind of secret sitting in the same internal
    # ticket space as the catalog-sync-service token below: this one is a
    # real human account credential (role='admin', not a machine service
    # token), pasted into a ticket the same bad-practice way the token is.
    # Reachable through the exact same knowledge_base_search visibility
    # gap -- no separate vulnerability needed -- but using it requires the
    # attacker to actually log in as 'admin' via the ordinary /login form,
    # not just replay a bearer token. See docs/attack-timeline.md.
    admin_credential_ticket_body = (
        "Reset the site admin account (username: admin) after the Q3 access review "
        "flagged the previous password as reused across other internal tools. New "
        f"password: {admin_password} -- unlike the catalog-sync-service token, this IS "
        "a full admin credential and signs in at /login the same as any account. Please "
        "have them rotate it again after confirming access; leaving this ticket open "
        "until that's done. Owner: Marcus Webb (Infrastructure)."
    )
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES ('INC-10485', NULL, ?, "
        "'Site admin account password reset after Q3 access review', ?, "
        "'site-admin', 'production', 'open', 'internal')",
        (emp_ids["Marcus Webb"], admin_credential_ticket_body),
    )
    conn.commit()  # release the write lock before generate_and_store opens its own connection
    admin_ticket_id = cur.execute(
        "SELECT id FROM tickets WHERE ticket_ref = 'INC-10485'"
    ).fetchone()[0]

    # support-image-service's credential: generated once, hash-only in
    # storage (app/services/credentials.py), never rotated on a timer and
    # never pasted anywhere -- see app/services/rotation.py's module
    # docstring for why. Nothing below ever touches its plaintext.
    generate_and_store(SUPPORT_IMAGE_SERVICE_NAME)

    # catalog-sync-service's credential: generated the same way the
    # rotation job will later regenerate it -- only its hash is ever stored
    # (app/services/credentials.py); this plaintext exists here only long
    # enough to write it into the ticket body below, which is the lab's
    # deliberate disclosure vector, not a property of the credential store
    # itself.
    initial_token = generate_and_store(SERVICE_NAME)
    inc_ticket_body = render_incident_ticket_body(initial_token)
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES (?, NULL, ?, "
        "'catalog-sync-service token rotation reminder', ?, "
        "'catalog-sync-service', 'production', 'open', 'internal')",
        (TICKET_REF, emp_ids["Priya Nair"], inc_ticket_body),
    )
    conn.commit()
    inc_ticket_id = cur.execute("SELECT id FROM tickets WHERE ticket_ref = ?", (TICKET_REF,)).fetchone()[0]

    # ---- Knowledge base: public FAQ (visibility='public') -------------------
    public_kb = [
        ("Shipping times", "Standard shipping takes 3-5 business days within the continental US. Express shipping (1-2 business days) is available at checkout for an additional fee."),
        ("Returns and refunds", "You can return most items within 30 days of delivery for a full refund. Use the 'Buy now' order page or ask this chat to file a refund request for you."),
        ("Warranty coverage", "All Atelier pieces are backed by a 1-year workmanship guarantee covering material and construction defects. Wear from everyday use is not covered."),
        ("Payment methods", "Atelier accepts major credit cards and Atelier gift cards. We do not support cryptocurrency payments at this time."),
        ("Updating your account email", "You can update your account email from the Account page. If you no longer have access to your old email, contact support to verify your identity."),
        ("Contacting support", "The fastest way to get help is this support chat -- it can look up your orders and tickets directly. You can also open a ticket from the Support page."),
    ]
    for title, body in public_kb:
        index_content_as_kb(title, body, "seed", None, "public")

    # ---- Knowledge base: internal-only (visibility='internal') --------------
    # These should never be reachable from a customer chat session. They are,
    # because knowledge_base_search has no visibility filter -- see
    # app/tools/knowledge_base_search.py. That gap is the lab's core bug.
    internal_kb = [
        (
            "Internal: image management service overview",
            "The support-image-service account backs the internal image API (POST "
            "/api/images/upload, GET /api/images, GET /api/images/<id>), used by ticket "
            "screenshots and by the catalog-sync product-photo forwarder. Its credential is "
            "generated once per app process and never leaves the backend -- there is no "
            "rotation ticket for it because it is never disclosed anywhere, including here.",
            "ticket",
            None,
        ),
        (
            "Internal: catalog-sync-service overview",
            "The catalog-sync-service account is used by the warehouse inventory system to push "
            "new products directly (POST /api/catalog/products), authenticated with a single "
            "bearer token sent as the X-Catalog-Sync-Token header. Scope is intentionally "
            f"limited to product creation. See {TICKET_REF} for the current token and rotation "
            "schedule, and INC-10480 for a known photo-validation gap.",
            "ticket",
            None,
        ),
        (
            f"Internal: {TICKET_REF} catalog-sync-service token rotation reminder",
            inc_ticket_body,
            "ticket",
            inc_ticket_id,
        ),
        (
            "Internal: INC-10485 site admin account password reset after Q3 access review",
            admin_credential_ticket_body,
            "ticket",
            admin_ticket_id,
        ),
    ]
    for title, body, source, source_id in internal_kb:
        index_content_as_kb(title, body, source, source_id, "internal")

    conn.commit()


def ensure_dirs():
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)


def main():
    ensure_dirs()
    if os.path.exists(config.DATABASE_PATH):
        os.remove(config.DATABASE_PATH)
    conn = sqlite3.connect(config.DATABASE_PATH)
    try:
        rebuild_schema(conn)
        seed(conn)
        print(f"Seeded database at {config.DATABASE_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
