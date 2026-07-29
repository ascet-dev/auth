"""Регрессы по находкам ревью: защита системного app, lockout, status, archived, bootstrap."""

import asyncio
import datetime

import pytest

from models.enums import IdentityStatus, SessionStatus


@pytest.fixture
async def auth_headers(owner_tokens):
    return {"Authorization": f"Bearer {owner_tokens['access_token']}"}


@pytest.fixture
async def admin_headers(client, app, auth_headers):
    """Заголовки НЕ-owner админа (роль ADMIN)."""
    resp = await client.post("/auth/register/password", json={"login": "admin2@x.com", "password": "secret123"})
    identity_id = resp.json()["identity_id"]
    resp = await client.post(
        "/admin/grants",
        json={"identity_id": identity_id, "role": "ADMIN"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post("/admin/auth/login", json={"login": "admin2@x.com", "password": "secret123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------- системный client_app


async def test_system_client_app_is_protected(client, app, auth_headers, admin_headers):
    admin_app = await app.get_admin_client_app()

    # ни ADMIN, ни OWNER не могут заархивировать системное приложение
    for headers in (admin_headers, auth_headers):
        resp = await client.delete(f"/admin/client-apps/{admin_app.id}", headers=headers)
        assert resp.status_code == 403, resp.text

        resp = await client.patch(
            f"/admin/client-apps/{admin_app.id}",
            json={"refresh_token_ttl_sec": 315360000},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    # админка продолжает работать
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 200


async def test_reserved_and_duplicate_keys_rejected(client, auth_headers):
    resp = await client.post(
        "/admin/client-apps",
        json={"key": "auth-admin", "name": "Fake admin"},
        headers=auth_headers,
    )
    assert resp.status_code == 403

    resp = await client.post("/admin/client-apps", json={"key": "dup", "name": "A"}, headers=auth_headers)
    assert resp.status_code == 200
    resp = await client.post("/admin/client-apps", json={"key": "dup", "name": "B"}, headers=auth_headers)
    assert resp.status_code == 409


async def test_archived_client_app_cannot_be_used(client, app, auth_headers, test_client_app):
    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    refresh_token = resp.json()["refresh_token"]

    resp = await client.delete(f"/admin/client-apps/{test_client_app.id}", headers=auth_headers)
    assert resp.status_code == 200

    # новый логин закрыт
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400
    assert "archived" in resp.json()["message"].lower()

    # и refresh существующей сессии тоже
    resp = await client.post(
        "/auth/session/refresh",
        json={"refresh_token": refresh_token, "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------- lockout


async def test_lockout_not_bypassable_by_concurrency(client, app, test_client_app):
    """Параллельные неверные попытки должны довести счётчик до лимита."""
    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})

    payload = {"login": "u@x.com", "password": "wrong", "client_app_id": str(test_client_app.id)}
    await asyncio.gather(*[client.post("/auth/login/password", json=payload) for _ in range(10)])

    credentials = await app.dao.credentials.search(identifier="u@x.com", archived=False)
    assert credentials[0].failed_attempts >= 5
    assert credentials[0].locked_until is not None

    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401


async def test_lockout_state_is_not_observable(client, app, test_client_app):
    """Ответ на залоченную учётку неотличим от несуществующей (enumeration)."""
    await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})

    payload = {"login": "u@x.com", "password": "wrong", "client_app_id": str(test_client_app.id)}
    for _ in range(6):
        await client.post("/auth/login/password", json=payload)

    credentials = await app.dao.credentials.search(identifier="u@x.com", archived=False)
    assert credentials[0].locked_until is not None

    locked = await client.post("/auth/login/password", json=payload)
    unknown = await client.post(
        "/auth/login/password",
        json={"login": "nobody@x.com", "password": "wrong", "client_app_id": str(test_client_app.id)},
    )
    assert locked.status_code == unknown.status_code == 401
    assert locked.json()["message"] == unknown.json()["message"] == "Invalid credentials"


async def test_expired_lockout_resets_counter(client, app, test_client_app):
    """После истечения окна счётчик обнуляется — бессрочно держать учётку залоченной нельзя."""
    resp = await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    credentials = await app.dao.credentials.search(identifier="u@x.com", archived=False)
    credential = credentials[0]

    # naive UTC: колонка timestamp without time zone, поэтому приводим явно,
    # иначе тест зависел бы от таймзоны машины
    past = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(minutes=1)
    await app.dao.credentials.update_by_id(credential.id, failed_attempts=5, locked_until=past)

    # одна неверная попытка после окна = счётчик 1, а не «снова 5 → блок»
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "wrong", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401
    credentials = await app.dao.credentials.search(identifier="u@x.com", archived=False)
    assert credentials[0].failed_attempts == 1
    assert credentials[0].locked_until is None

    # верный пароль работает
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------- identity.status


async def test_blocked_identity_cannot_login_or_refresh(client, app, test_client_app):
    resp = await client.post("/auth/register/password", json={"login": "u@x.com", "password": "secret123"})
    identity_id = resp.json()["identity_id"]

    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    refresh_token = resp.json()["refresh_token"]
    session_id = resp.json()["session"]["id"]

    await app.dao.identities.update_by_id(identity_id, status=IdentityStatus.BLOCKED)

    # refresh отказывает и ревокает сессию
    resp = await client.post(
        "/auth/session/refresh",
        json={"refresh_token": refresh_token, "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 401
    session = await app.dao.sessions.get_by_id(session_id)
    assert session.status == SessionStatus.REVOKED

    # новый логин тоже не выдаёт токен
    resp = await client.post(
        "/auth/login/password",
        json={"login": "u@x.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    assert resp.status_code == 400
    assert "not active" in resp.json()["message"].lower()


async def test_blocked_admin_cannot_login(client, app, owner):
    await app.dao.identities.update_by_id(owner["identity_id"], status=IdentityStatus.BLOCKED)

    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "Invalid credentials"


# ---------------------------------------------------------------- bootstrap_owner


async def test_bootstrap_refuses_existing_credential(client, app, clean_db):
    """Публично зарегистрированный 'admin' не должен молча стать владельцем."""
    await app.bootstrap_owner("owner", "s3cret")
    grant = await app.get_active_admin_grant(
        (await app.dao.credentials.search(identifier="owner", archived=False))[0].identity_id,
    )
    await app.dao.admin_grants.archive_by_id(grant.id)

    # злоумышленник зарегистрировал такой же логин
    attacker = await app.register_password_identity("owner2", "attacker-pass")

    with pytest.raises(ValueError, match="already exists"):
        await app.bootstrap_owner("owner2", "operator-pass")

    assert await app.get_active_admin_grant(attacker.id) is None

    # с явным флагом — грант выдаётся, но пароль оператора применяется
    result = await app.bootstrap_owner("owner2", "operator-pass", adopt_existing=True)
    assert result["created"] is True
    assert await app.get_active_admin_grant(attacker.id) is not None

    resp = await client.post("/admin/auth/login", json={"login": "owner2", "password": "attacker-pass"})
    assert resp.status_code == 401
    resp = await client.post("/admin/auth/login", json={"login": "owner2", "password": "operator-pass"})
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------- прочие находки ревью


async def test_connector_settings_are_typed(client, auth_headers):
    resp = await client.post(
        "/admin/connectors",
        json={"key": "p", "type": "PASSWORD", "name": "P", "settings": {"max_failed_attempts": "many"}},
        headers=auth_headers,
    )
    assert resp.status_code == 400

    # строковое число приводится к int, а не уезжает в JSONB как строка
    resp = await client.post(
        "/admin/connectors",
        json={"key": "p", "type": "PASSWORD", "name": "P", "settings": {"max_failed_attempts": "3"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["settings"]["max_failed_attempts"] == 3

    # неизвестные ключи не принимаются
    resp = await client.post(
        "/admin/connectors",
        json={"key": "p2", "type": "PASSWORD", "name": "P2", "settings": {"whatever": 1}},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_oauth_connector_cannot_be_broken_by_null(client, auth_headers):
    resp = await client.post(
        "/admin/connectors",
        json={
            "key": "g",
            "type": "OAUTH",
            "name": "G",
            "settings": {"client_id": "c", "client_secret": "s", "auth_url": "a", "token_url": "t"},
        },
        headers=auth_headers,
    )
    connector_id = resp.json()["id"]

    resp = await client.patch(
        f"/admin/connectors/{connector_id}",
        json={"settings": {"auth_url": None}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    resp = await client.get(f"/admin/connectors/{connector_id}", headers=auth_headers)
    assert resp.json()["settings"]["auth_url"] == "a"


async def test_secret_masked_in_get_and_can_be_cleared(client, auth_headers):
    resp = await client.post(
        "/admin/connectors",
        json={"key": "tma-1", "type": "TMA", "name": "Bot", "settings": {"bot_token": "1:secret"}},
        headers=auth_headers,
    )
    connector_id = resp.json()["id"]

    # GET по id и list — секрет не отдаётся
    resp = await client.get(f"/admin/connectors/{connector_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert "bot_token" not in resp.json()["settings"]
    assert resp.json()["settings"]["bot_token_set"] is True

    resp = await client.get("/admin/connectors", headers=auth_headers)
    assert all("bot_token" not in item["settings"] for item in resp.json()["items"])

    # обязательный секрет нельзя очистить пустой строкой — только заменить
    resp = await client.patch(
        f"/admin/connectors/{connector_id}",
        json={"settings": {"bot_token": ""}},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "cannot be cleared" in resp.json()["message"]

    # замена секрета работает, PATCH других полей его не трогает
    resp = await client.patch(
        f"/admin/connectors/{connector_id}",
        json={"settings": {"bot_token": "2:new-secret"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["settings"]["bot_token_set"] is True

    resp = await client.patch(f"/admin/connectors/{connector_id}", json={"name": "Renamed"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["settings"]["bot_token_set"] is True


async def test_admin_cannot_revoke_grants(client, app, auth_headers, admin_headers, owner):
    grant = await app.get_active_admin_grant(owner["identity_id"])
    resp = await client.delete(f"/admin/grants/{grant.id}", headers=admin_headers)
    assert resp.status_code == 403


async def test_explicit_null_in_patch_is_ignored(client, auth_headers):
    """{"name": null} — «не менять», а не NOT NULL violation с 500."""
    resp = await client.post("/admin/client-apps", json={"key": "app-x", "name": "App X"}, headers=auth_headers)
    app_id = resp.json()["id"]

    resp = await client.patch(
        f"/admin/client-apps/{app_id}",
        json={"name": None, "refresh_token_ttl_sec": 7200},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "App X"
    assert resp.json()["refresh_token_ttl_sec"] == 7200

    # только null-ы = нечего менять
    resp = await client.patch(f"/admin/client-apps/{app_id}", json={"name": None}, headers=auth_headers)
    assert resp.status_code == 400


async def test_concurrent_duplicate_create_is_conflict(client, auth_headers):
    """Гонка на unique-индексе — 409, а не 500."""
    payloads = [{"key": "race", "name": f"App {i}"} for i in range(5)]
    results = await asyncio.gather(
        *[client.post("/admin/client-apps", json=p, headers=auth_headers) for p in payloads],
    )
    codes = sorted(r.status_code for r in results)
    assert codes[0] == 200
    assert set(codes[1:]) == {409}, [r.text for r in results]


async def test_admin_cannot_revoke_owner_session(client, app, owner, owner_tokens, admin_headers):
    """ADMIN не выбивает владельца из его же админки."""
    session_id = owner_tokens["session"]["id"]
    resp = await client.delete(f"/admin/sessions/{session_id}", headers=admin_headers)
    assert resp.status_code == 403, resp.text

    session = await app.dao.sessions.get_by_id(session_id)
    assert session.status == SessionStatus.ACTIVE


async def test_grant_not_found_is_404(client, auth_headers):
    resp = await client.delete("/admin/grants/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


async def test_bootstrap_state_not_leaked_to_anonymous(client, app, clean_db):
    """Сообщение про 'run bootstrap-owner' не должно уходить неаутентифицированному."""
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "Invalid credentials"
