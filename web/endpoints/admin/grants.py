from adc_aiopg.types import Paginated
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from models.enums import AdminRole
from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminEndpoint, AdminList, Conflict, conflict_on_unique, dump_entity


class AdminListGrants(AdminList):
    doc = Doc(tags=["admin", "grants"], summary="List admin grants")
    table = "admin_grants"
    query = s.GrantSearch
    response = Response(Paginated[s.GrantRead])


class AdminCreateGrant(AdminEndpoint):
    doc = Doc(tags=["admin", "grants"], summary="Grant admin role (OWNER only)")
    require_role = AdminRole.OWNER

    body = s.GrantCreate
    response = Response(s.GrantRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app, conflict_on_unique():
            try:
                grant = await app.grant_admin_role(
                    identity_id=ctx.body.identity_id,
                    role=ctx.body.role,
                    granted_by=app.current_admin.identity.id,
                )
            except ValueError as e:
                raise Conflict(message=str(e)) from e
            return dump_entity(grant)


class AdminRevokeGrant(AdminEndpoint):
    doc = Doc(tags=["admin", "grants"], summary="Revoke admin grant (OWNER only)")
    require_role = AdminRole.OWNER

    query = s.ByIdPath
    response = Response(OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                await app.revoke_admin_grant(ctx.query.id)
            except ValueError as e:
                raise Conflict(message=str(e)) from e
            return {"ok": True}
