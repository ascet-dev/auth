"""Smoke-тесты существующего пользовательского флоу — валидируют харнесс."""


async def test_liveness(client):
    resp = await client.get("/liveness")
    assert resp.status_code == 200


async def test_register_login_refresh(client, test_client_app):
    # register
    resp = await client.post(
        "/auth/register/password",
        json={"login": "user@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    identity_id = resp.json()["identity_id"]
    assert identity_id

    # login
    resp = await client.post(
        "/auth/login/password",
        json={
            "login": "user@example.com",
            "password": "secret123",
            "client_app_id": str(test_client_app.id),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["session"]["identity_id"] == identity_id
    assert "refresh_token_hash" not in body["session"]

    # refresh (ротация)
    resp = await client.post(
        "/auth/session/refresh",
        json={"refresh_token": body["refresh_token"], "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 200, resp.text
    refreshed = resp.json()
    assert refreshed["refresh_token"] != body["refresh_token"]

    # старый refresh инвалидирован
    resp = await client.post(
        "/auth/session/refresh",
        json={"refresh_token": body["refresh_token"], "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401, resp.text


async def test_login_wrong_password(client, test_client_app):
    await client.post("/auth/register/password", json={"login": "u2@example.com", "password": "secret123"})

    resp = await client.post(
        "/auth/login/password",
        json={"login": "u2@example.com", "password": "wrong", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401
