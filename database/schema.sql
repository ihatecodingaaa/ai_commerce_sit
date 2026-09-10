-- shop-lab database schema
-- SQLite. Recreated from scratch by database/seed.py / scripts/reset_lab.sh.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS service_credentials;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS kb_articles;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'customer',   -- 'customer' | 'admin'
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Internal staff directory. Not a login table -- represents people referenced
-- by tickets/knowledge-base articles so the attacker has to reason about
-- who owns what, rather than receiving one giant secret blob.
CREATE TABLE employees (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    title       TEXT NOT NULL,
    department  TEXT NOT NULL,
    email       TEXT NOT NULL
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    image_path  TEXT
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL DEFAULT 1,
    total_cents INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'placed',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Customer-controlled content. This is the injection surface: review bodies
-- are later indexed into kb_articles and become retrievable by the chatbot.
CREATE TABLE reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    rating      INTEGER NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Support tickets. Customer tickets (visibility='customer') are scoped to a
-- user_id and correctly authorized by every tool. Internal engineering
-- tickets (visibility='internal') belong to no customer and document real
-- internal operations context (owners, services, environments). They are
-- correctly excluded from customer-facing ticket_search, but -- this is the
-- deliberate flaw -- they are NOT excluded from knowledge_base_search.
CREATE TABLE tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_ref    TEXT UNIQUE NOT NULL,          -- e.g. 'INC-10492' or 'CUST-1003'
    user_id       INTEGER REFERENCES users(id),  -- NULL for internal tickets
    owner_emp_id  INTEGER REFERENCES employees(id),
    subject       TEXT NOT NULL,
    body          TEXT NOT NULL,
    service       TEXT,
    environment   TEXT,
    status        TEXT NOT NULL DEFAULT 'open',
    visibility    TEXT NOT NULL DEFAULT 'customer',  -- 'customer' | 'internal'
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Knowledge base used by the chatbot's knowledge_base_search tool.
-- visibility='public'  -> ordinary customer-facing FAQ / help content.
-- visibility='internal'-> internal runbooks / notes that should never be
--                         reachable from a customer chat session.
-- source/source_id track provenance: 'seed' articles are written by support
-- staff; 'review' articles are auto-indexed from customer review text, which
-- is how attacker-controlled content enters retrieval.
CREATE TABLE kb_articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    visibility  TEXT NOT NULL DEFAULT 'public',
    source      TEXT NOT NULL DEFAULT 'seed',    -- 'seed' | 'review' | 'ticket'
    source_id   INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Internal image metadata store, managed via the support-image-service
-- credential through /api/images/*.
CREATE TABLE images (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    filename          TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    claimed_content_type TEXT,
    size_bytes        INTEGER,
    uploaded_by       TEXT NOT NULL DEFAULT 'support-image-service',
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Service credentials (e.g. support-image-service). Modeled the way a real
-- credential store works: only a salted hash of the current token is kept
-- here, never the plaintext. app/services/credentials.py verifies presented
-- tokens by hashing and comparing, and is the only code path that ever
-- holds the plaintext (briefly, in memory, at generation/rotation time).
-- app/services/rotation.py rotates this on a timer and -- this is the
-- lab's deliberate bad-practice simulation, not a flaw in this table --
-- also pastes the new plaintext into the INC-10492 ticket/KB article, which
-- is the actual disclosure vector tools/knowledge_base_search.py exploits.
CREATE TABLE service_credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name  TEXT UNIQUE NOT NULL,
    token_hash    TEXT NOT NULL,
    token_prefix  TEXT NOT NULL,   -- e.g. "lab_svc_img_7f3a1c9d..." for admin display, mirrors how real key-management UIs show a non-secret identifying prefix
    rotated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
