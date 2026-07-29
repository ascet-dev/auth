from __future__ import annotations

from typing import TYPE_CHECKING

from adc_aiopg import RowNotFoundError
from adc_aiopg.types import Paginated
from adc_webkit.errors import Forbidden, NotFound
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from services.service import AUTH_ADMIN_CLIENT_KEY
from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminArchive, AdminCreate, AdminGet, AdminList, AdminUpdate, Conflict, conflict_on_unique

if TYPE_CHECKING:
    from uuid import UUID

    from services import App


async def _forbid_system_app(app: App, client_app_id: UUID) -> None:
    """
    Системное приложение auth-admin неизменяемо через API: его архивация
    или смена TTL ломает вход в саму админку для всех, включая OWNER-а.
    """
    try:
        client_app = await app.dao.client_apps.get_by_id(client_app_id)
    except RowNotFoundError:
        raise NotFound(message="Not found") from None
    if client_app.key == AUTH_ADMIN_CLIENT_KEY:
        raise Forbidden(message=f"System client app '{AUTH_ADMIN_CLIENT_KEY}' cannot be modified")


class AdminListClientApps(AdminList):
    doc = Doc(tags=["admin", "client-apps"], summary="List client apps")
    table = "client_apps"
    query = s.ClientAppSearch
    response = Response(Paginated[s.ClientAppRead])


class AdminGetClientApp(AdminGet):
    doc = Doc(tags=["admin", "client-apps"], summary="Get client app")
    table = "client_apps"
    query = s.ClientAppPath
    response = Response(s.ClientAppRead)


class AdminCreateClientApp(AdminCreate):
    doc = Doc(tags=["admin", "client-apps"], summary="Create client app")
    table = "client_apps"
    body = s.ClientAppCreate
    response = Response(s.ClientAppRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            if ctx.body.key == AUTH_ADMIN_CLIENT_KEY:
                raise Forbidden(message=f"Key '{AUTH_ADMIN_CLIENT_KEY}' is reserved for the admin UI")

            existing = await app.dao.client_apps.search(key=ctx.body.key, archived=False, limit=1)
            if existing:
                raise Conflict(message=f"Client app with key '{ctx.body.key}' already exists")

            async with conflict_on_unique():
                entity = await self.dao(app).create(**self.build_create_payload(ctx))
            return self.serialize(entity)


class AdminUpdateClientApp(AdminUpdate):
    doc = Doc(tags=["admin", "client-apps"], summary="Update client app (key immutable)")
    table = "client_apps"
    query = s.ClientAppPath
    body = s.ClientAppUpdate
    response = Response(s.ClientAppRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            await _forbid_system_app(app, ctx.query.id)
        return await super().execute(ctx)


class AdminArchiveClientApp(AdminArchive):
    doc = Doc(tags=["admin", "client-apps"], summary="Archive client app (soft delete)")
    table = "client_apps"
    query = s.ClientAppPath
    response = Response(OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            await _forbid_system_app(app, ctx.query.id)
        return await super().execute(ctx)
