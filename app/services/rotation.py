"""Background rotation for the support-image-service credential, plus the
lab's deliberate bad-practice simulation: every rotation pastes the new
plaintext value into the INC-10492 ticket (and its mirrored KB article),
exactly like an engineer manually updating a "here's the current token"
note after rotating a credential. See app/services/credentials.py for the
actual storage model (hash-only) -- that part is realistic on its own;
this module is what re-creates the leak on every rotation so the lab's
disclosure vector always matches whatever token is presently valid.

Runs as a daemon thread started once from app/__init__.py::create_app().
Never runs during tests (guarded by `"pytest" not in sys.modules`) --
tests call rotate_support_image_service_token() directly instead, so the
rotation logic itself is still fully covered without a real-time wait.
"""
import sys
import threading
import time

from app.logging_setup import log_event
from app.models.db import execute, query_one
from app.services.credentials import generate_and_store

SERVICE_NAME = "support-image-service"
TICKET_REF = "INC-10492"

_scheduler_started = False
_scheduler_lock = threading.Lock()


def render_incident_ticket_body(token: str) -> str:
    """Shared template so the seed data and every later rotation produce
    identically-worded content, differing only in the current token value.
    """
    return (
        "Reminder: rotate the support-image-service bearer token used for the internal "
        "image-management API (POST /api/images/upload, GET /api/images, GET /api/images/<id>). "
        f"Current token: {token} -- this grants read access to ticket "
        "screenshot metadata and upload rights only, it is not an admin credential and cannot "
        "reach other internal systems. Owner: Alice Tan (Customer Operations). "
        "Do not paste this token into any customer-facing channel, including support chat. "
        "Related: INC-10480 (upload validation gap, still open). "
        "This token rotates automatically -- if it stops working, this ticket has the "
        "current value."
    )


def rotate_support_image_service_token() -> str:
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


def _scheduler_loop(interval_seconds: int):
    while True:
        time.sleep(interval_seconds)
        try:
            rotate_support_image_service_token()
        except Exception as exc:  # noqa: BLE001 - a rotation failure must not kill the thread
            log_event("service_credential_rotation_error", service_name=SERVICE_NAME, error=str(exc))


def start_rotation_scheduler(interval_seconds: int):
    """Start the background rotation thread exactly once per process.
    No-ops under pytest (rotation logic is tested by calling
    rotate_support_image_service_token() directly, deterministically,
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
