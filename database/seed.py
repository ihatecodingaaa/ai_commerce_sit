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
from app.services.rotation import SERVICE_NAME, render_incident_ticket_body  # noqa: E402

SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"


def rebuild_schema(conn: sqlite3.Connection):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def seed(conn: sqlite3.Connection):
    cur = conn.cursor()

    # ---- Customers -----------------------------------------------------
    customers = [
        ("alice.customer", "alice.customer@example-lab.test", "Customer123!", "Alice Customer"),
        ("bob.customer", "bob.customer@example-lab.test", "Customer123!", "Bob Customer"),
    ]
    customer_ids = {}
    for username, email, pw, full_name in customers:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'customer')",
            (username, email, hash_password(pw), full_name),
        )
        customer_ids[username] = cur.lastrowid

    # ---- Admin account ----------------------------------------------------
    # Logs in through the same /login route as any customer; the ONLY thing
    # that grants admin capability is role='admin' on this row. Self-
    # registration (app/routes/auth_routes.py) always hardcodes
    # role='customer' and has no field to request otherwise -- admin
    # accounts only ever come from seed data, never from a signup form.
    cur.execute(
        "INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("admin", "admin@shoplite-lab.test", hash_password("AdminLab123!"), "Site Administrator"),
    )

    # ---- Employees (directory only, not login accounts) -----------------
    employees = [
        ("Alice Tan", "Head of Customer Operations", "Customer Operations", "alice.tan@shoplite-lab.test"),
        ("Priya Nair", "Platform Engineer", "Infrastructure", "priya.nair@shoplite-lab.test"),
        ("Marcus Webb", "Site Reliability Engineer", "Infrastructure", "marcus.webb@shoplite-lab.test"),
        ("Dana Okafor", "Support Team Lead", "Customer Operations", "dana.okafor@shoplite-lab.test"),
    ]
    emp_ids = {}
    for name, title, dept, email in employees:
        cur.execute(
            "INSERT INTO employees (name, title, department, email) VALUES (?, ?, ?, ?)",
            (name, title, dept, email),
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
        "'Image upload API trusts client Content-Type header', "
        "'support-image-service validates uploads by checking the multipart Content-Type "
        "header instead of sniffing file contents. Low severity, filed for tracking. "
        "See INC-10492 for the related credential-rotation reminder.', "
        "'support-image-service', 'production', 'open', 'internal')",
        (emp_ids["Priya Nair"],),
    )
    conn.commit()  # release the write lock before generate_and_store opens its own connection

    # Generate a fresh, random support-image-service credential the same
    # way the rotation job will later regenerate it -- only its hash is
    # ever stored (app/services/credentials.py); this plaintext exists
    # here only long enough to write it into the ticket body below, which
    # is the lab's deliberate disclosure vector, not a property of the
    # credential store itself.
    initial_token = generate_and_store(SERVICE_NAME)
    inc_10492_body = render_incident_ticket_body(initial_token)
    cur.execute(
        "INSERT INTO tickets (ticket_ref, user_id, owner_emp_id, subject, body, service, environment, status, visibility) "
        "VALUES ('INC-10492', NULL, ?, "
        "'support-image-service token rotation reminder', ?, "
        "'support-image-service', 'production', 'open', 'internal')",
        (emp_ids["Alice Tan"], inc_10492_body),
    )
    conn.commit()
    inc_10492_id = cur.execute("SELECT id FROM tickets WHERE ticket_ref = 'INC-10492'").fetchone()[0]

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
            "The support-image-service account is used by staff tooling to store ticket "
            "screenshot attachments via the internal image API (POST /api/images/upload, "
            "GET /api/images, GET /api/images/<id>). It authenticates with a single bearer "
            "token sent as the X-Service-Token header. Scope is intentionally limited: it can "
            "read ticket image metadata and upload images. It cannot escalate to an admin role "
            "and has no access to other internal systems. See INC-10492 for the current token "
            "and rotation schedule, and INC-10480 for a known upload-validation gap.",
            "ticket",
            None,
        ),
        (
            "Internal: INC-10492 support-image-service token rotation reminder",
            inc_10492_body,
            "ticket",
            inc_10492_id,
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
