"""Тесты admin CRUD API: ресурсы, маскировка секретов, OWNER-only гранты."""

import pytest

from models.enums import SessionStatus


@pytest.fixture
async def auth_headers(owner_tokens):
    return {"Authorization": f"Bearer {owner_tokens['access_token']}"}


async def test_client_apps_crud(client, auth_headers):
    # create
    resp = await client.post(
        "/admin/client-apps",
        json={"key": "my-app", "name": "My App"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    app_id = resp.json()["id"]
    assert resp.json()["key"] == "my-app"

    # list (auth-admin из bootstrap + my-app)
    resp = await client.get("/admin/client-apps", headers=auth_headers)
    assert resp.status_code == 200
    keys = {item["key"] for item in resp.json()["items"]}
    assert {"my-app", "auth-admin"} <= keys
    assert resp.json()["pagination"]["total"] >= 2

    # get
    resp = await client.get(f"/admin/client-apps/{app_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "My App"

    # patch
    resp = await client.patch(
        f"/admin/client-apps/{app_id}",
        json={"name": "Renamed", "refresh_token_ttl_sec": 3600},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["refresh_token_ttl_sec"] == 3600

    # archive
    resp = await client.delete(f"/admin/client-apps/{app_id}", headers=auth_headers)
    assert resp.status_code == 200

    # архивные пропадают из выдачи по умолчанию
    resp = await client.get("/admin/client-apps", headers=auth_headers)
    assert "my-app" not in {item["key"] for item in resp.json()["items"]}

    # но видны с archived=true
    resp = await client.get("/admin/client-apps?archived=true", headers=auth_headers)
    assert "my-app" in {item["key"] for item in resp.json()["items"]}


async def test_client_apps_404(client, auth_headers):
    resp = await client.get("/admin/client-apps/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


async def test_identities_list_and_detail(client, app, auth_headers, owner):
    resp = await client.get("/admin/identities", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] >= 1

    detail = await client.get(f"/admin/identities/{owner['identity_id']}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["identity"]["id"] == str(owner["identity_id"])
    assert body["grant"]["role"] == "OWNER"
    creds = body["credentials"]
    assert len(creds) == 1
    assert creds[0]["identifier"] == "admin"
    assert "secret_hash" not in creds[0]


async def test_sessions_list_and_revoke(client, app, auth_headers, owner_tokens):
    resp = await client.get("/admin/sessions", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all("refresh_token_hash" not in item for item in items)

    session_id = owner_tokens["session"]["id"]
    resp = await client.delete(f"/admin/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200

    session = await app.dao.sessions.get_by_id(session_id)
    assert session.status == SessionStatus.REVOKED


async def test_logins_audit(client, auth_headers):
    # логин овнера уже записан фикстурой owner_tokens
    resp = await client.get("/admin/logins?method=admin_password", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["method"] == "admin_password"
    assert items[0]["success"] is True


async def test_grants_flow(client, app, auth_headers):
    # создаём обычную учётку
    resp = await client.post("/auth/register/password", json={"login": "admin2@x.com", "password": "secret123"})
    identity_id = resp.json()["identity_id"]

    # выдаём ADMIN
    resp = await client.post(
        "/admin/grants",
        json={"identity_id": identity_id, "role": "ADMIN"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    grant_id = resp.json()["id"]
    assert resp.json()["role"] == "ADMIN"
    assert resp.json()["granted_by"] is not None

    # повторная выдача — конфликт
    resp = await client.post(
        "/admin/grants",
        json={"identity_id": identity_id, "role": "ADMIN"},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # новый админ может логиниться в админку
    resp = await client.post("/admin/auth/login", json={"login": "admin2@x.com", "password": "secret123"})
    assert resp.status_code == 200
    admin2_access = resp.json()["access_token"]
    admin2_headers = {"Authorization": f"Bearer {admin2_access}"}

    # ...но не выдавать гранты (не OWNER)
    resp = await client.post(
        "/admin/grants",
        json={"identity_id": identity_id, "role": "ADMIN"},
        headers=admin2_headers,
    )
    assert resp.status_code == 403

    # отзыв гранта OWNER-ом ревокает и админские сессии admin2
    resp = await client.delete(f"/admin/grants/{grant_id}", headers=auth_headers)
    assert resp.status_code == 200

    resp = await client.get("/admin/auth/me", headers=admin2_headers)
    assert resp.status_code == 401


async def test_cannot_revoke_last_owner(client, app, auth_headers, owner):
    grant = await app.get_active_admin_grant(owner["identity_id"])
    resp = await client.delete(f"/admin/grants/{grant.id}", headers=auth_headers)
    assert resp.status_code == 409
    assert "last active owner" in resp.json()["message"].lower()


async def test_admin_endpoints_require_auth(client):
    resp = await client.get("/admin/client-apps")
    assert resp.status_code == 401
