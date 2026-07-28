"""Тесты админ-аутентификации: bootstrap, login, guard, refresh с отозванным grant."""

from models.enums import AdminRole, SessionStatus


async def test_bootstrap_idempotent(app, clean_db):
    first = await app.bootstrap_owner("admin", "admin")
    assert first["created"] is True

    second = await app.bootstrap_owner("admin", "admin")
    assert second["created"] is False
    assert second["identity_id"] == first["identity_id"]

    # ровно один активный OWNER grant
    owners = await app.dao.admin_grants.search(role=AdminRole.OWNER, archived=False)
    assert len(owners) == 1


async def test_admin_login_success(client, owner):
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert "refresh_token_hash" not in body["session"]


async def test_admin_login_wrong_password_and_lockout(client, owner):
    for _ in range(5):
        resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "wrong"})
        assert resp.status_code == 401

    # 6-я попытка отбита блокировкой — ответ неотличим от неверного пароля
    # (иначе состояние блокировки выдавало бы существование учётки)
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "Invalid credentials"


async def test_admin_login_without_grant(client, app, owner):
    """Учётка с паролем, но без гранта — тот же Invalid credentials."""
    resp = await client.post("/auth/register/password", json={"login": "user@example.com", "password": "secret123"})
    assert resp.status_code == 200

    resp = await client.post("/admin/auth/login", json={"login": "user@example.com", "password": "secret123"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "Invalid credentials"


async def test_user_token_rejected_on_admin_endpoint(client, app, owner, test_client_app):
    """Пользовательский JWT (без role) не проходит admin_jwt guard."""
    await client.post("/auth/register/password", json={"login": "user@example.com", "password": "secret123"})
    resp = await client.post(
        "/auth/login/password",
        json={"login": "user@example.com", "password": "secret123", "client_app_id": str(test_client_app.id)},
    )
    user_access = resp.json()["access_token"]

    resp = await client.get("/admin/auth/me", headers={"Authorization": f"Bearer {user_access}"})
    assert resp.status_code == 401


async def test_admin_me(client, owner, owner_tokens):
    resp = await client.get(
        "/admin/auth/me",
        headers={"Authorization": f"Bearer {owner_tokens['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["identity_id"] == str(owner["identity_id"])
    assert body["role"] == "OWNER"


async def test_admin_refresh_rotates(client, owner_tokens):
    resp = await client.post("/admin/auth/refresh", json={"refresh_token": owner_tokens["refresh_token"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["refresh_token"] != owner_tokens["refresh_token"]


async def test_refresh_with_revoked_grant_revokes_session(client, app, owner, owner_tokens):
    # Отзываем грант
    grant = await app.get_active_admin_grant(owner["identity_id"])
    await app.dao.admin_grants.archive_by_id(grant.id)

    resp = await client.post("/admin/auth/refresh", json={"refresh_token": owner_tokens["refresh_token"]})
    assert resp.status_code == 401

    # Сессия ревокнута
    session_id = owner_tokens["session"]["id"]
    session = await app.dao.sessions.get_by_id(session_id)
    assert session.status == SessionStatus.REVOKED


async def test_me_with_revoked_grant(client, app, owner, owner_tokens):
    """Отзыв гранта действует сразу: даже живой access-токен получает 401."""
    grant = await app.get_active_admin_grant(owner["identity_id"])
    await app.dao.admin_grants.archive_by_id(grant.id)

    resp = await client.get(
        "/admin/auth/me",
        headers={"Authorization": f"Bearer {owner_tokens['access_token']}"},
    )
    assert resp.status_code == 401
