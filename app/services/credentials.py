"""Generic service-credential storage, modeled on how a real secrets/API-key
store actually works (e.g. GitHub tokens, Stripe API keys): a high-entropy
random value is generated once, only its SHA-256 hash is ever persisted to
the database, and verifying a presented token means hashing it and doing a
constant-time comparison -- the plaintext is never read back out of
storage, because storage never has it.

The one place plaintext exists after generation is a short-lived in-process
cache (`_plaintext_cache`), which exists ONLY so this lab's rotation job
(app/services/rotation.py) can paste the freshly generated value into the
INC-10492 ticket/KB article -- simulating an engineer who rotates a
credential and pastes it into a ticket as a "here's the new value" note.
That paste is the lab's deliberate bad practice and the actual
vulnerability; this module's storage itself follows real-world practice
throughout.

`get_current_plaintext_for_admin()` mirrors a real secret manager's
authorized "get secret value" administrative API (e.g. AWS Secrets Manager
GetSecretValue) -- available to trusted server-side/instructor code and
tests, never exposed through any customer- or chatbot-facing route.
"""
import hashlib
import hmac
import secrets as pysecrets
import threading

from app.logging_setup import log_event
from app.models.db import execute, query_one

_cache_lock = threading.Lock()
_plaintext_cache: dict[str, str] = {}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_and_store(service_name: str) -> str:
    """Generate a new random token for `service_name`, persist only its
    hash, and return the plaintext (the only time this function does).
    """
    plaintext = f"lab_svc_img_{pysecrets.token_hex(16)}"
    token_hash = _hash(plaintext)
    prefix = plaintext[:20] + "..."

    existing = query_one(
        "SELECT id FROM service_credentials WHERE service_name = ?", (service_name,)
    )
    if existing:
        execute(
            "UPDATE service_credentials SET token_hash = ?, token_prefix = ?, "
            "rotated_at = datetime('now') WHERE service_name = ?",
            (token_hash, prefix, service_name),
        )
    else:
        execute(
            "INSERT INTO service_credentials (service_name, token_hash, token_prefix) "
            "VALUES (?, ?, ?)",
            (service_name, token_hash, prefix),
        )

    with _cache_lock:
        _plaintext_cache[service_name] = plaintext

    log_event(
        "service_credential_generated",
        service_name=service_name,
        token_prefix=prefix,
    )
    return plaintext


def verify(service_name: str, presented_token: str) -> bool:
    """Constant-time verification against the stored hash. Never touches
    the plaintext cache -- this is what a real verification path looks
    like: hash what was presented, compare to what's stored.
    """
    if not presented_token:
        return False
    row = query_one(
        "SELECT token_hash FROM service_credentials WHERE service_name = ?", (service_name,)
    )
    if not row:
        return False
    return hmac.compare_digest(row["token_hash"], _hash(presented_token))


def get_current_plaintext_for_admin(service_name: str) -> str | None:
    """Authorized administrative accessor only -- see module docstring.
    Not reachable from any HTTP route; used by app/services/rotation.py and
    by tests/instructor tooling that need to know "what's currently valid"
    the same way an admin console would.
    """
    with _cache_lock:
        return _plaintext_cache.get(service_name)
