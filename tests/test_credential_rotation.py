"""Verifies the catalog-sync-service credential behaves like a real
service credential: randomly generated, stored only as a hash, verified in
constant time, and rotated -- with the old value invalidated and the
INC-10493 ticket/KB article updated to the new one (the lab's deliberate
disclosure vector staying in sync with whatever is currently valid).

support-image-service's credential is covered separately in
tests/test_support_image_service_credential.py -- it behaves the same way
under the hood (same generate/store/verify code), but is never rotated on
a timer or disclosed anywhere, so it has no equivalent "stays in sync
with the ticket" test.
"""
import re

from app.models.db import query_all, query_one
from app.services.credentials import (
    generate_and_store,
    get_current_plaintext_for_admin,
    verify,
)
from app.services.rotation import SERVICE_NAME, TICKET_REF, rotate_catalog_sync_service_token


def test_generated_tokens_are_random_not_static(alice):
    a = generate_and_store("some-other-test-service")
    b = generate_and_store("some-other-test-service")
    assert a != b, "each generation must produce a fresh random value"
    assert a.startswith("lab_svc_img_")


def test_only_a_hash_is_persisted_never_the_plaintext(catalog_sync_token):
    row = query_one(
        "SELECT token_hash, token_prefix FROM service_credentials WHERE service_name = ?",
        (SERVICE_NAME,),
    )
    assert row is not None
    assert row["token_hash"] != catalog_sync_token
    assert catalog_sync_token not in row["token_hash"]
    # sha256 hex digest
    assert re.fullmatch(r"[0-9a-f]{64}", row["token_hash"])
    # the admin-facing prefix is a truncated, clearly-non-secret preview
    assert row["token_prefix"].startswith("lab_svc_img_")
    assert row["token_prefix"] != catalog_sync_token


def test_verify_accepts_current_and_rejects_garbage(catalog_sync_token):
    assert verify(SERVICE_NAME, catalog_sync_token) is True
    assert verify(SERVICE_NAME, catalog_sync_token + "x") is False
    assert verify(SERVICE_NAME, "") is False
    assert verify(SERVICE_NAME, "totally-made-up") is False


def test_rotation_invalidates_the_old_token_and_issues_a_new_one(catalog_sync_token):
    old_token = catalog_sync_token
    new_token = rotate_catalog_sync_service_token()

    assert new_token != old_token
    assert verify(SERVICE_NAME, new_token) is True
    assert verify(SERVICE_NAME, old_token) is False, "rotation must invalidate the previous token"
    assert get_current_plaintext_for_admin(SERVICE_NAME) == new_token


def test_rotation_updates_the_disclosure_ticket_and_kb_article(catalog_sync_token):
    new_token = rotate_catalog_sync_service_token()

    ticket = query_one("SELECT body FROM tickets WHERE ticket_ref = ?", (TICKET_REF,))
    assert new_token in ticket["body"]
    assert catalog_sync_token not in ticket["body"], "the old token must not linger in the ticket text"

    kb_rows = query_all(
        "SELECT kb.body FROM kb_articles kb "
        "JOIN tickets t ON kb.source = 'ticket' AND kb.source_id = t.id "
        "WHERE t.ticket_ref = ?",
        (TICKET_REF,),
    )
    assert kb_rows, "expected the mirrored internal KB article to exist"
    assert all(new_token in row["body"] for row in kb_rows)
