"""Service-credential storage: a high-entropy token is generated once, only
its SHA-256 hash is persisted to the database, and verifying a presented
token hashes it and compares in constant time. The plaintext is never read
back out of storage.

A short-lived in-process cache (`_plaintext_cache`) holds the plaintext
after generation so same-process callers can use it without a storage
round-trip; a freshly started process starts with an empty cache.
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
    """Return the current plaintext for same-process callers (e.g. the
    rotation job); None if this process has not generated it.
    """
    with _cache_lock:
        return _plaintext_cache.get(service_name)
