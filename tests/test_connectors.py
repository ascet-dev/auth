"""Тесты коннекторов: CRUD, маскировка секретов, резолв в login-флоу, M2M на приложения."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest


@pytest.fixture
async def auth_headers(owner_tokens):
    return {"Authorization": f"Bearer {owner_tokens['access_token']}"}


def make_init_data(bot_token: str, telegram_id: int, username: str = "tester") -> str:
    """Собирает initData, подписанный токеном бота (как это делает Telegram)."""
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "AAEtest",
        "user": json.dumps({"id": telegram_id, "first_name": "T", "username": username}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hash": signature})


async def create_connector(client, headers, **kwargs):
    resp = await client.post("/admin/connectors", json=kwargs, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def map_connectors(client, headers, app_id, connector_ids):
    resp = await client.put(
        f"/admin/client-apps/{app_id}/connectors",
        json={"connector_ids": connector_ids},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------- дефолты без коннекторов


async def test_builtin_defaults_without_connectors(client, test_client_app):
    """Нет ни одного коннектора → пароль работает на встроенной политике."""
    resp = await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------- CRUD и маскировка


async def test_connector_crud_and_secret_masking(client, auth_headers):
    connector = await create_connector(
        client,
        auth_headers,
        key="google-web",
        type="OAUTH",
        name="Google (web)",
        settings={
            "client_id": "cid",
            "client_secret": "super-secret",
            "auth_url": "https://accounts.google.com/o/oauth2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
        },
    )
    assert connector["settings"]["client_secret_set"] is True
    assert "client_secret" not in connector["settings"]

    # PATCH без секрета не стирает его
    resp = await client.patch(
        f"/admin/connectors/{connector['id']}",
        json={"settings": {"client_id": "cid2"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["settings"]["client_id"] == "cid2"
    assert resp.json()["settings"]["client_secret_set"] is True

    # дубликат key → 409
    resp = await client.post(
        "/admin/connectors",
        json={
            "key": "google-web",
            "type": "OAUTH",
            "name": "dup",
            "settings": {"client_id": "x", "client_secret": "y", "auth_url": "a", "token_url": "t"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # обязательные settings при создании
    resp = await client.post(
        "/admin/connectors",
        json={"key": "tma-x", "type": "TMA", "name": "no token", "settings": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "bot_token" in resp.json()["message"]


async def test_oauth_start_flow_uses_connector(client, auth_headers, test_client_app):
    await create_connector(
        client,
        auth_headers,
        key="google-web",
        type="OAUTH",
        name="Google",
        settings={
            "client_id": "my-client-id",
            "client_secret": "s",
            "auth_url": "https://accounts.google.com/o/oauth2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
        },
    )
    resp = await client.post(
        "/auth/oauth/start",
        json={"provider": "google-web", "redirect_uri": "https://app/cb"},
    )
    assert resp.status_code == 200, resp.text
    assert "my-client-id" in resp.json()["redirect_url"]


# ---------------------------------------------------------------- парольные политики per-app


async def test_password_policy_from_connector(client, app, auth_headers, test_client_app):
    """max_failed_attempts=3 из коннектора вместо дефолтных 5."""
    connector = await create_connector(
        client,
        auth_headers,
        key="password-strict",
        type="PASSWORD",
        name="Strict policy",
        settings={"max_failed_attempts": 3, "lockout_minutes": 60},
    )
    await map_connectors(client, auth_headers, str(test_client_app.id), [connector["id"]])

    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})

    for _ in range(3):
        resp = await client.post(
            "/auth/login/password",
            json={"login": "u@x.com", "password": "wrong", "client_app_id": str(test_client_app.id)},
        )
        assert resp.status_code == 401

    # после 3 неудач верный пароль тоже отбит (блокировка), ответ обезличенный
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401
    credentials = await app.dao.credentials.search(identifier="u@x.com", archived=False)
    assert credentials[0].locked_until is not None


async def test_registration_disabled_by_connector(client, auth_headers, test_client_app):
    connector = await create_connector(
        client,
        auth_headers,
        key="password-closed",
        type="PASSWORD",
        name="No self-registration",
        settings={"allow_registration": False},
    )
    await map_connectors(client, auth_headers, str(test_client_app.id), [connector["id"]])

    resp = await client.post(
        "/auth/register/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400
    assert "registration is disabled" in resp.json()["message"].lower()


# ---------------------------------------------------------------- два TMA-бота на два приложения


async def test_two_tma_bots_two_apps(client, app, auth_headers, test_client_app):
    bot_a_token = "111:AAA-token"
    bot_b_token = "222:BBB-token"

    connector_a = await create_connector(
        client,
        auth_headers,
        key="tma-bot-a",
        type="TMA",
        name="Bot A",
        settings={"bot_token": bot_a_token},
    )
    connector_b = await create_connector(
        client,
        auth_headers,
        key="tma-bot-b",
        type="TMA",
        name="Bot B",
        settings={"bot_token": bot_b_token},
    )

    resp = await client.post(
        "/admin/client-apps",
        json={"key": "app-b", "name": "App B"},
        headers=auth_headers,
    )
    app_b = resp.json()

    app_a_id = str(test_client_app.id)
    await map_connectors(client, auth_headers, app_a_id, [connector_a["id"]])
    await map_connectors(client, auth_headers, app_b["id"], [connector_b["id"]])

    telegram_id = 424242
    init_data_a = make_init_data(bot_a_token, telegram_id)
    init_data_b = make_init_data(bot_b_token, telegram_id)

    # логин в app A подписью бота A — ок
    resp = await client.post("/auth/tma/login", json={"init_data": init_data_a, "client_app_id": app_a_id})
    assert resp.status_code == 200, resp.text
    identity_a = resp.json()["session"]["identity_id"]

    # подпись бота A в app B (там бот B) — невалидная подпись
    resp = await client.post("/auth/tma/login", json={"init_data": init_data_a, "client_app_id": app_b["id"]})
    assert resp.status_code == 401

    # тот же телеграм-юзер через бота B в app B → та же identity (глобальный telegram_id)
    resp = await client.post("/auth/tma/login", json={"init_data": init_data_b, "client_app_id": app_b["id"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["session"]["identity_id"] == identity_a

    # connector_key записан в credential
    credentials = await app.dao.credentials.search(external_subject_id=str(telegram_id), archived=False)
    assert len(credentials) == 1
    assert credentials[0].provider == "tma-bot-b"  # последний использованный


async def test_multiple_tma_for_one_app_requires_connector_key(client, auth_headers, test_client_app):
    bot_a_token = "111:AAA-token"
    connector_a = await create_connector(
        client,
        auth_headers,
        key="tma-a",
        type="TMA",
        name="A",
        settings={"bot_token": bot_a_token},
    )
    connector_b = await create_connector(
        client,
        auth_headers,
        key="tma-b",
        type="TMA",
        name="B",
        settings={"bot_token": "222:BBB"},
    )
    app_id = str(test_client_app.id)
    await map_connectors(client, auth_headers, app_id, [connector_a["id"], connector_b["id"]])

    init_data = make_init_data(bot_a_token, 1001)

    # без явного коннектора — ошибка выбора
    resp = await client.post("/auth/tma/login", json={"init_data": init_data, "client_app_id": app_id})
    assert resp.status_code == 400
    assert "specify connector" in resp.json()["message"].lower()

    # с явным — ок
    resp = await client.post(
        "/auth/tma/login",
        json={"init_data": init_data, "client_app_id": app_id, "connector": "tma-a"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------- whitelist приложения


async def test_app_whitelist_blocks_other_methods(client, auth_headers, test_client_app):
    connector = await create_connector(
        client,
        auth_headers,
        key="tma-only",
        type="TMA",
        name="TMA",
        settings={"bot_token": "1:X"},
    )
    app_id = str(test_client_app.id)
    await map_connectors(client, auth_headers, app_id, [connector["id"]])

    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": app_id},
    )
    assert resp.status_code == 400
    assert "not allowed for this application" in resp.json()["message"]


async def test_mapping_validation(client, auth_headers, test_client_app):
    p1 = await create_connector(client, auth_headers, key="p1", type="PASSWORD", name="P1", settings={})
    p2 = await create_connector(client, auth_headers, key="p2", type="PASSWORD", name="P2", settings={})

    # два password-коннектора на приложение — конфликт
    resp = await client.put(
        f"/admin/client-apps/{test_client_app.id}/connectors",
        json={"connector_ids": [p1["id"], p2["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # маппинг и замена
    mapped = await map_connectors(client, auth_headers, str(test_client_app.id), [p1["id"]])
    assert [c["id"] for c in mapped] == [p1["id"]]

    resp = await client.get(f"/admin/client-apps/{test_client_app.id}/connectors", headers=auth_headers)
    assert [c["id"] for c in resp.json()] == [p1["id"]]

    # очистка маппинга = все включённые коннекторы
    mapped = await map_connectors(client, auth_headers, str(test_client_app.id), [])
    assert mapped == []


async def test_disabled_connector_blocks_login(client, auth_headers, test_client_app):
    connector = await create_connector(
        client,
        auth_headers,
        key="password-main",
        type="PASSWORD",
        name="Main",
        settings={},
    )
    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})

    resp = await client.patch(
        f"/admin/connectors/{connector['id']}",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["message"].lower()

    # админ-логин не зависит от коннекторов
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 200
