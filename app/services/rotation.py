"""Background rotation for the catalog-sync-service credential, plus the
lab's deliberate bad-practice simulation: every rotation pastes the new
plaintext value into the INC-10493 ticket (and its mirrored KB article),
exactly like an engineer manually updating a "here's the current token"
note after rotating a credential. See app/services/credentials.py for the
actual storage model (hash-only) -- that part is realistic on its own;
this module is what re-creates the leak on every rotation so the lab's
disclosure vector always matches whatever token is presently valid.

Runs as a daemon thread started once from app/__init__.py::create_app().
Never runs during tests (guarded by `"pytest" not in sys.modules`) --
tests call rotate_catalog_sync_service_token() directly instead, so the
rotation logic itself is still fully covered without a real-time wait.

catalog-sync-service is the ONLY credential this module ever discloses.
support-image-service (used by app/services/image_client.py -- admin
ticket screenshots, and now also the catalog-sync photo forwarder) has
its own credential too, generated once per process by
ensure_support_image_service_credential() below, but it is never rotated
on a timer and never pasted anywhere. Keeping exactly one credential in
the leak path is what keeps this lab's vulnerability to a single,
findable chain instead of two parallel ones -- see docs/attack-timeline.md.
"""
import sys
import threading
import time

from app.logging_setup import log_event
from app.models.db import execute, query_one
from app.services.credentials import generate_and_store

SERVICE_NAME = "catalog-sync-service"
TICKET_REF = "INC-10493"

SUPPORT_IMAGE_SERVICE_NAME = "support-image-service"

_scheduler_started = False
_scheduler_lock = threading.Lock()


def render_incident_ticket_body(token: str) -> str:
    """Shared template so the seed data and every later rotation produce
    identically-worded content, differing only in the current token value.
    """
    return (
        "Reminder: rotate the catalog-sync-service bearer token used by the warehouse "
        "inventory system to push new products directly (POST /api/catalog/products). "
        f"Current token: {token} -- this grants product-creation rights only, it is not "
        "an admin credential and cannot reach other internal systems. Owner: Priya Nair "
        "(Infrastructure). Do not paste this token into any customer-facing channel, "
        "including support chat. This token rotates automatically -- if it stops "
        "working, this ticket has the current value."
    )


def rotate_catalog_sync_service_token() -> str:
    """Generate a new token, store its hash, and update the ticket/KB
    article that (deliberately) mirrors the current plaintext. Returns the
    new plaintext (callers that don't need it -- e.g. the scheduler -- can
    ignore it; the credential store never needs it again after this call).
    """
    new_token = generate_and_store(SERVICE_NAME)
    new_body = render_incident_ticket_body(new_token)

    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (TICKET_REF,))
    if ticket:
        execute("UPDATE tickets SET body = ? WHERE id = ?", (new_body, ticket["id"]))
        execute(
            "UPDATE kb_articles SET body = ? WHERE source = 'ticket' AND source_id = ?",
            (new_body, ticket["id"]),
        )

    log_event("service_credential_rotated", service_name=SERVICE_NAME, ticket_ref=TICKET_REF)
    return new_token


def ensure_support_image_service_credential() -> str:
    """Generate a fresh support-image-service credential in THIS process so
    app/services/image_client.py's in-process calls (admin ticket
    screenshots, catalog-sync photo forwarding) work immediately after
    startup -- seeding happens in a separate `python database/seed.py`
    process whose in-memory credential cache never reaches the running
    app. Unlike catalog-sync-service, nothing here ever discloses the
    result anywhere, so there's no ticket/KB update to keep in sync.

    Returns the new plaintext so callers (image_client.py's self-healing
    retry, in particular) can use it immediately without a second
    round-trip through get_current_plaintext_for_admin.
    """
    return generate_and_store(SUPPORT_IMAGE_SERVICE_NAME)


def _scheduler_loop(interval_seconds: int):
    # Rotates once immediately (not just after the first `interval_seconds`
    # sleep) so the INC-10493 ticket reflects a token that's actually valid
    # in this process as soon as the app starts, rather than whatever
    # seed.py (a different process) happened to write.
    while True:
        try:
            rotate_catalog_sync_service_token()
        except Exception as exc:  # noqa: BLE001 - a rotation failure must not kill the thread
            log_event("service_credential_rotation_error", service_name=SERVICE_NAME, error=str(exc))
        time.sleep(interval_seconds)


def start_rotation_scheduler(interval_seconds: int):
    """Start the background rotation thread exactly once per process.
    No-ops under pytest (rotation logic is tested by calling
    rotate_catalog_sync_service_token() directly, deterministically,
    instead of waiting on a timer).
    """
    global _scheduler_started
    if "pytest" in sys.modules:
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    thread = threading.Thread(
        target=_scheduler_loop, args=(interval_seconds,), name="token-rotation", daemon=True
    )
    thread.start()
    log_event(
        "service_credential_rotation_scheduler_started",
        service_name=SERVICE_NAME,
        interval_seconds=interval_seconds,
    )
