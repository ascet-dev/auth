"""Регрессы на эскалацию привилегий ADMIN → OWNER и обход выделенного админ-логина."""

import pytest

from tests.test_connectors import create_connector, make_init_data


@pytest.fixture
async def auth_headers(owner_tokens):
    return {"Authorization": f"Bearer {owner_tokens['access_token']}"}


@pytest.fixture
async def admin_headers(client, auth_headers):
    """Заголовки не-owner админа (роль ADMIN)."""
    resp = await client.post("/auth/register/password", json={"login": "admin2@x.com", "password": "secret123"})
    identity_id = resp.json()["identity_id"]
    resp = await client.post(
        "/admin/grants",
        json={"identity_id": identity_id, "role": "ADMIN"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post("/admin/auth/login", json={"login": "admin2@x.com", "password": "secret123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_public_login_cannot_use_system_client_app(client, app, owner):
    """
    Публичные login-эндпоинты не должны выдавать сессию под системным приложением:
    именно по его key выдаётся claim `role`, то есть это обход login_by_admin.
    """
    admin_app = await app.get_admin_client_app()

    resp = await client.post(
        "/auth/login/password",
        json={"login": "admin", "password": "admin", "client_app_id": str(admin_app.id)},
    )
    assert resp.status_code == 400, resp.text
    assert "reserved" in resp.json()["message"].lower()

    resp = await client.post(
        "/auth/tma/login",
        json={"init_data": "whatever", "client_app_id": str(admin_app.id)},
    )
    assert resp.status_code == 400


async def test_admin_cannot_create_connectors(client, admin_headers):
    """Коннектор = возможность выпускать сессии за чужую identity, поэтому только OWNER."""
    resp = await client.post(
        "/admin/connectors",
        json={"key": "evil-bot", "type": "TMA", "name": "Evil", "settings": {"bot_token": "666:EVIL"}},
        headers=admin_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_admin_cannot_remap_connectors(client, app, admin_headers, auth_headers):
    resp = await client.post("/admin/client-apps", json={"key": "app-x", "name": "X"}, headers=auth_headers)
    app_id = resp.json()["id"]

    resp = await client.put(
        f"/admin/client-apps/{app_id}/connectors",
        json={"connector_ids": []},
        headers=admin_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_full_escalation_chain_is_broken(client, app, owner, auth_headers, admin_headers):
    """
    Полная цепочка из ревью: ADMIN заводит TMA-коннектор со своим ботом,
    подделывает initData с telegram_id владельца и логинится под системным
    приложением → токен {sub: owner, role: OWNER}. Должна рваться на каждом шаге.
    """
    telegram_id = 777001
    owner_identity_id = owner["identity_id"]
    # у владельца есть TMA-credential (он хоть раз входил через бота)
    await app.dao.credentials.create(
        identity_id=owner_identity_id,
        type="TMA",
        provider="legit-bot",
        external_subject_id=str(telegram_id),
        failed_attempts=0,
    )

    evil_token = "666:EVIL-bot-token"  # noqa: S105

    # шаг 1: ADMIN не может завести коннектор
    resp = await client.post(
        "/admin/connectors",
        json={"key": "evil-bot", "type": "TMA", "name": "Evil", "settings": {"bot_token": evil_token}},
        headers=admin_headers,
    )
    assert resp.status_code == 403

    # шаг 2: даже если коннектор существует (заведён владельцем), под системным
    # приложением публичный TMA-логин не проходит
    await create_connector(
        client,
        auth_headers,
        key="evil-bot",
        type="TMA",
        name="Evil",
        settings={"bot_token": evil_token},
    )
    admin_app = await app.get_admin_client_app()
    forged = make_init_data(evil_token, telegram_id)

    resp = await client.post(
        "/auth/tma/login",
        json={"init_data": forged, "client_app_id": str(admin_app.id), "connector": "evil-bot"},
    )
    assert resp.status_code == 400, resp.text
    assert "reserved" in resp.json()["message"].lower()
