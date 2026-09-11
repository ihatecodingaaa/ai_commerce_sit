"""Rebuild the lab database from schema.sql and load deterministic seed data.

Run directly: `python database/seed.py`
Also invoked by scripts/reset_lab.sh.

Everything here is fake training data. Passwords are simple on purpose --
this is a lab, not a security control under test at the account-creation
layer -- but they are still hashed the same way real registrations are.
"""
import os
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


def rebuild_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed(conn: sqlite3.Connection):
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
    cur.execute(
        "INSERT INTO users (username, email, password_hash, full_name, role, avatar) VALUES (?, ?, ?, ?, 'admin', ?)",
        ("admin", "admin@shoplite-lab.test", hash_password("AdminLab123!"), "Site Administrator", "robot"),
    )

    # ---- Employees (directory only, not login accounts) -----------------
    # `photo` is a filename under app/static/team/ -- placeholders shipped
    # with the repo; see app/static/team/README.md for how to swap them.
    employees = [
        ("Alice Tan", "Head of Customer Operations", "Customer Operations", "alice.tan@shoplite-lab.test", "alice-tan.jpg"),
        ("Priya Nair", "Platform Engineer", "Infrastructure", "priya.nair@shoplite-lab.test", "priya-nair.jpg"),
        ("Marcus Webb", "Site Reliability Engineer", "Infrastructure", "marcus.webb@shoplite-lab.test", "marcus-webb.jpg"),
        ("Dana Okafor", "Support Team Lead", "Customer Operations", "dana.okafor@shoplite-lab.test", "dana-okafor.svg"),
    ]
    emp_ids = {}
    for name, title, dept, email, photo in employees:
        cur.execute(
            "INSERT INTO employees (name, title, department, email, photo) VALUES (?, ?, ?, ?, ?)",
            (name, title, dept, email, photo),
        )
        emp_ids[name] = cur.lastrowid

    # ---- Products ---------------------------------------------------------
    products = [
        ("Aurora Wireless Earbuds", "Audio", 5999, "Compact true-wireless earbuds with 24h battery life and active noise cancellation."),
        ("Pulse Fitness Band", "Wearables", 3499, "Lightweight fitness tracker with heart-rate monitoring and 7-day battery."),
        ("Nimbus Portable SSD 1TB", "Storage", 8999, "USB-C portable SSD, up to 1050MB/s read speeds, shock resistant."),
        ("Lumen Smart Desk Lamp", "Home", 2999, "Adjustable smart desk lamp with app-controlled brightness and color temperature."),
        ("Voyager Travel Charger", "Accessories", 1999, "65W GaN USB-C charger with three ports for laptops, phones, and tablets."),
        ("Echo Mini Bluetooth Speaker", "Audio", 2499, "Palm-sized Bluetooth speaker with surprisingly big sound and IPX6 rating."),
    ]
    product_ids = []
    for name, category, price, desc in products:
        cur.execute(
            "INSERT INTO products (name, category, price_cents, description) VALUES (?, ?, ?, ?)",
            (name, category, price, desc),
        )
        product_ids.append(cur.lastrowid)

    # ---- Orders (seed history for alice.customer) --------------------------
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 1, 5999, 'delivered')",
        (customer_ids["alice.customer"], product_ids[0]),
    )
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 2, 3998, 'shipped')",
        (customer_ids["alice.customer"], product_ids[4]),
    )
    cur.execute(
        "INSERT INTO orders (user_id, product_id, quantity, total_cents, status) VALUES (?, ?, 1, 8999, 'placed')",
        (customer_ids["bob.customer"], product_ids[2]),
    )

    # ---- Cart (seed one item so /cart isn't empty on first login) -----------
    cur.execute(
        "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, 1)",
        (customer_ids["alice.customer"], product_ids[3]),
    )

    # ---- Reviews (legitimate seed reviews) ----------------------------------
    cur.execute(
        "INSERT INTO reviews (product_id, user_id, rating, body) VALUES (?, ?, 5, ?)",
        (product_ids[0], customer_ids["bob.customer"], "Great sound and the battery really does last all day. Shipping was fast too."),
    )
    cur.execute(
        "INSERT INTO reviews (product_id, user_id, rating, body) VALUES (?, ?, 4, ?)",
        (product_ids[2], customer_ids["alice.customer"], "Fast drive, feels well built. Wish it came with a carrying pouch."),
    )
    conn.commit()

    # index those seed reviews the same way the app does at runtime
    for row in cur.execute("SELECT id, product_id, body FROM reviews").fetchall():
        product_name = cur.execute("SELECT name FROM products WHERE id = ?", (row[1],)).fetchone()[0]
        index_content_as_kb(f"Customer review: {product_name}", row[2], "review", row[0], "public")

    # ---- Customer support ticket (visibility='customer') --------------------
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES ('CUST-10021', ?, ?, 'Question about earbuds warranty', "
        "'Hi, do the Aurora Wireless Earbuds come with a 1-year warranty in my region?', "
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
    conn.commit()  # release the write lock before generate_and_store opens its own connection

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
        ("Warranty coverage", "All ShopLite electronics come with a standard 1-year manufacturer warranty covering defects. Accidental damage is not covered."),
        ("Payment methods", "ShopLite accepts major credit cards and ShopLite gift cards. We do not support cryptocurrency payments at this time."),
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
