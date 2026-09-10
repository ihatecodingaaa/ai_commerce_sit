def test_register_and_login(client):
    resp = client.post(
        "/register",
        data={
            "username": "newcustomer1",
            "email": "newcustomer1@example-lab.test",
            "full_name": "New Customer",
            "password": "Sup3rSecret!",
        },
    )
    assert resp.status_code in (302, 200)

    client.post("/logout")

    resp = client.post("/login", data={"username": "newcustomer1", "password": "Sup3rSecret!"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/account")


def test_login_wrong_password_rejected(client):
    resp = client.post("/login", data={"username": "alice.customer", "password": "wrong"})
    assert resp.status_code == 401


def test_account_page_requires_login(client):
    resp = client.get("/account")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
