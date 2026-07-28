from __future__ import annotations

from typing import Any

from adc_aiopg import RowNotFoundError
from adc_aiopg.types import Paginated
from adc_webkit.errors import BadRequest, NotFound
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from models.enums import AuthMethod
from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminArchive, AdminEndpoint, AdminList, Conflict, dump_entity

# Секретные ключи settings: наружу отдаётся только флаг <key>_set
SECRET_SETTINGS_KEYS = ("bot_token", "client_secret")

# Обязательные settings при создании коннектора
REQUIRED_SETTINGS: dict[AuthMethod, tuple[str, ...]] = {
    AuthMethod.PASSWORD: (),
    AuthMethod.OTP: (),
    AuthMethod.TMA: ("bot_token",),
    AuthMethod.OAUTH: ("client_id", "client_secret", "auth_url", "token_url"),
}


def serialize_connector(entity: Any) -> dict:
    data = dump_entity(entity)
    settings = dict(data.get("settings") or {})
    for secret_key in SECRET_SETTINGS_KEYS:
        has_value = bool(settings.pop(secret_key, None))
        if has_value:
            settings[f"{secret_key}_set"] = True
    data["settings"] = settings
    return data


def merge_settings(current: dict | None, patch: dict) -> dict:
    """Merge по ключам; секреты: None = не менять, '' = очистить."""
    merged = dict(current or {})
    for key, value in patch.items():
        if key in SECRET_SETTINGS_KEYS:
            if value is None:
                continue
            if value == "":
                merged.pop(key, None)
                continue
        merged[key] = value
    return merged


class AdminListConnectors(AdminList):
    doc = Doc(tags=["admin", "connectors"], summary="List auth connectors")
    table = "connectors"
    query = s.ConnectorSearch
    response = Response(Paginated[s.ConnectorRead])

    def serialize(self, entity: Any) -> dict:
        return serialize_connector(entity)


class AdminGetConnector(AdminEndpoint):
    doc = Doc(tags=["admin", "connectors"], summary="Get connector")
    query = s.ByIdPath
    response = Response(s.ConnectorRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                connector = await app.dao.connectors.get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Connector not found") from None
            return serialize_connector(connector)


class AdminCreateConnector(AdminEndpoint):
    doc = Doc(tags=["admin", "connectors"], summary="Create auth connector")
    body = s.ConnectorCreate
    response = Response(s.ConnectorRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            connector_type = AuthMethod(ctx.body.type)

            missing = [k for k in REQUIRED_SETTINGS[connector_type] if not ctx.body.settings.get(k)]
            if missing:
                raise BadRequest(message=f"Missing required settings for {connector_type}: {', '.join(missing)}")

            existing = await app.dao.connectors.search(key=ctx.body.key, archived=False, limit=1)
            if existing:
                raise Conflict(message=f"Connector with key '{ctx.body.key}' already exists")

            connector = await app.dao.connectors.create(
                key=ctx.body.key,
                type=connector_type,
                name=ctx.body.name,
                enabled=ctx.body.enabled,
                settings=merge_settings(None, ctx.body.settings),
            )
            return serialize_connector(connector)


class AdminUpdateConnector(AdminEndpoint):
    doc = Doc(tags=["admin", "connectors"], summary="Update connector (key/type immutable)")
    query = s.ByIdPath
    body = s.ConnectorUpdate
    response = Response(s.ConnectorRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                connector = await app.dao.connectors.get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Connector not found") from None

            payload: dict[str, Any] = {}
            patch = ctx.body.model_dump(exclude_unset=True)
            if "name" in patch and patch["name"] is not None:
                payload["name"] = patch["name"]
            if "enabled" in patch and patch["enabled"] is not None:
                payload["enabled"] = patch["enabled"]
            if patch.get("settings") is not None:
                payload["settings"] = merge_settings(connector.settings, patch["settings"])

            if not payload:
                raise BadRequest(message="Nothing to update")

            connector = await app.dao.connectors.update_by_id(connector.id, **payload)
            return serialize_connector(connector)


class AdminArchiveConnector(AdminArchive):
    doc = Doc(tags=["admin", "connectors"], summary="Archive connector (soft delete)")
    table = "connectors"
    query = s.ByIdPath
    response = Response(OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            # снимаем активные привязки к приложениям
            await app.dao.client_app_connectors.archive(connector_id=ctx.query.id, archived=False)
            try:
                await app.dao.connectors.archive_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Connector not found") from None
            return {"ok": True}


class AdminGetClientAppConnectors(AdminEndpoint):
    doc = Doc(tags=["admin", "client-apps"], summary="Connectors mapped to client app")
    query = s.ByIdPath
    response = Response(list[s.ConnectorRead])

    async def execute(self, ctx: Ctx) -> list:  # type: ignore[override, unused-ignore]
        async with self.admin_scope(ctx) as app:
            connector_ids = await app.list_app_connector_ids(ctx.query.id)
            if not connector_ids:
                return []
            connectors = await app.dao.connectors.search(id_in=list(connector_ids), archived=False)
            return [serialize_connector(c) for c in connectors]


class AdminSetClientAppConnectors(AdminEndpoint):
    doc = Doc(
        tags=["admin", "client-apps"],
        summary="Replace client app connector mapping (empty = all enabled connectors)",
    )
    query = s.ByIdPath
    body = s.ClientAppConnectorsUpdate
    response = Response(list[s.ConnectorRead])

    async def execute(self, ctx: Ctx) -> list:  # type: ignore[override, unused-ignore]
        async with self.admin_scope(ctx) as app:
            try:
                client_app = await app.dao.client_apps.get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Client app not found") from None

            wanted = set(ctx.body.connector_ids)
            connectors = await app.dao.connectors.search(id_in=list(wanted), archived=False) if wanted else []
            if len(connectors) != len(wanted):
                raise BadRequest(message="Some connectors do not exist or are archived")

            password_count = sum(1 for c in connectors if AuthMethod(c.type) == AuthMethod.PASSWORD)
            if password_count > 1:
                raise Conflict(message="At most one PASSWORD connector per application")

            current = await app.dao.client_app_connectors.search(client_app_id=client_app.id, archived=False)
            current_by_connector = {link.connector_id: link for link in current}

            for connector_id, link in current_by_connector.items():
                if connector_id not in wanted:
                    await app.dao.client_app_connectors.archive_by_id(link.id)
            for connector_id in wanted - set(current_by_connector):
                await app.dao.client_app_connectors.create(client_app_id=client_app.id, connector_id=connector_id)

            return [serialize_connector(c) for c in connectors]
