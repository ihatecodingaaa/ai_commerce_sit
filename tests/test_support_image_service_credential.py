"""support-image-service's credential is the "everything else should be
secure" half of the story: it exists, it works (app/services/image_client.py
uses it for admin ticket screenshots and catalog-sync photo forwarding),
but unlike catalog-sync-service, it is never rotated on a timer and never
pasted into any ticket or KB article -- so there should be no way to find
its plaintext anywhere a customer chat session (or its underlying
knowledge_base_search tool) can reach, and no other service's token
should work in its place.
"""
from app.models.db import query_all
from app.services.credentials import get_current_plaintext_for_admin
from app.services.rotation import SUPPORT_IMAGE_SERVICE_NAME


def test_support_image_service_token_never_appears_in_any_ticket_or_kb_body(service_token):
    for row in query_all("SELECT body FROM tickets"):
        assert service_token not in row["body"], "support-image-service token leaked into a ticket"
    for row in query_all("SELECT body FROM kb_articles"):
        assert service_token not in row["body"], "support-image-service token leaked into a KB article"


def test_catalog_sync_token_does_not_authenticate_to_the_internal_image_api(client, catalog_sync_token):
    """Cross-service token confusion must fail: /api/images/upload checks
    specifically against support-image-service's stored hash."""
    resp = client.get("/api/images", headers={"X-Service-Token": catalog_sync_token})
    assert resp.status_code == 401


def test_support_image_service_token_does_not_authenticate_to_catalog_sync(client, service_token):
    """And the reverse: /api/catalog/products checks specifically against
    catalog-sync-service's stored hash."""
    resp = client.post(
        "/api/catalog/products",
        headers={"X-Catalog-Sync-Token": service_token},
        data={"name": "x", "category": "x", "description": "x", "price": "9.99"},
    )
    assert resp.status_code == 401


def test_support_image_service_credential_is_warm_after_app_startup(client):
    """app/services/rotation.py::ensure_support_image_service_credential is
    what makes this true -- called once from create_app()."""
    assert get_current_plaintext_for_admin(SUPPORT_IMAGE_SERVICE_NAME) is not None
