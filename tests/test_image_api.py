import io


def test_upload_requires_service_token(client):
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"fake"), "photo.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401


def test_upload_rejects_wrong_token(client):
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"fake"), "photo.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": "not-the-real-token"},
    )
    assert resp.status_code == 401


def test_upload_succeeds_with_correct_token_and_allowed_type(client, service_token):
    resp = client.post(
        "/api/images/upload",
        data={"file": (io.BytesIO(b"\xff\xd8\xff\xe0fakejpegbytes"), "photo.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        headers={"X-Service-Token": service_token},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["processing"]["mode"] == "thumbnail"


def test_list_and_get_require_token(client, service_token):
    assert client.get("/api/images").status_code == 401
    assert client.get("/api/images/1").status_code == 401

    resp = client.get("/api/images", headers={"X-Service-Token": service_token})
    assert resp.status_code == 200
