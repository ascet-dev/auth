"""Тесты настройки способов входа: глобальные тумблеры, per-app whitelist, маскировка токена."""

import pytest


@pytest.fixture
async def auth_headers(owner_tokens):
    return {"Authorization": f"Bearer {owner_tokens['access_token']}"}


async def test_list_defaults(client, auth_headers):
    resp = await client.get("/admin/auth-methods", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    methods = {m["method"]: m for m in resp.json()}
    assert set(methods) == {"PASSWORD", "OTP", "TMA", "OAUTH"}
    assert methods["PASSWORD"]["enabled"] is True
    assert methods["PASSWORD"]["allow_registration"] is True
    assert methods["OTP"]["enabled"] is False
    # дефолты из кода, строк в БД ещё нет
    assert all(m["configured"] is False for m in methods.values())


async def test_disable_password_blocks_user_login_not_admin(client, app, auth_headers, test_client_app):
    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})

    resp = await client.patch("/admin/auth-methods/PASSWORD", json={"enabled": False}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["enabled"] is False
    assert resp.json()["configured"] is True

    # пользовательский логин закрыт
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["message"].lower()

    # регистрация тоже
    resp = await client.post("/auth/register/password", json={"login": "u2@x.com", "password": "secret123"})
    assert resp.status_code == 400

    # админ-логин работает всегда (guard не применяется)
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 200


async def test_registration_toggle(client, auth_headers, test_client_app):
    resp = await client.patch(
        "/admin/auth-methods/PASSWORD",
        json={"allow_registration": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["allow_registration"] is False
    assert resp.json()["enabled"] is True

    resp = await client.post("/auth/register/password", json={"login": "u3@x.com", "password": "secret123"})
    assert resp.status_code == 400
    assert "registration is disabled" in resp.json()["message"].lower()

    # существующие пользователи логинятся
    resp = await client.patch(
        "/admin/auth-methods/PASSWORD",
        json={"allow_registration": True},
        headers=auth_headers,
    )
    resp = await client.post("/auth/register/password", json={"login": "u3@x.com", "password": "secret123"})
    assert resp.status_code == 200


async def test_per_app_whitelist(client, app, auth_headers, owner):
    # приложение только с TMA
    resp = await client.post(
        "/admin/client-apps",
        json={"key": "tma-only", "name": "TMA Only", "allowed_auth_methods": ["tma"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    tma_app = resp.json()
    assert tma_app["allowed_auth_methods"] == ["tma"]

    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": tma_app["id"]},
    )
    assert resp.status_code == 400
    assert "not allowed for this application" in resp.json()["message"]


async def test_tma_bot_token_write_only(client, auth_headers):
    resp = await client.patch(
        "/admin/auth-methods/TMA",
        json={"bot_token": "123456:ABC-secret", "auth_date_max_age": 600},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bot_token_set"] is True
    assert body["auth_date_max_age"] == 600
    assert "bot_token" not in body

    # очистка токена пустой строкой
    resp = await client.patch("/admin/auth-methods/TMA", json={"bot_token": ""}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["bot_token_set"] is False


async def test_otp_disabled_by_default(app, clean_db):
    import pytest as _pytest

    with _pytest.raises(ValueError, match="disabled"):
        await app.send_otp("someone@x.com", "EMAIL")


async def test_update_requires_admin(client):
    resp = await client.patch("/admin/auth-methods/PASSWORD", json={"enabled": False})
    assert resp.status_code == 401
