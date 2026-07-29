from adc_aiopg import RowNotFoundError
from adc_aiopg.types import Paginated
from adc_webkit.errors import Forbidden, NotFound
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from models.enums import AdminRole, SessionStatus
from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminEndpoint, AdminList


class AdminListSessions(AdminList):
    doc = Doc(tags=["admin", "sessions"], summary="List sessions (all identities)")
    table = "sessions"
    query = s.SessionSearch
    response = Response(Paginated[s.SessionRead])


class AdminRevokeSession(AdminEndpoint):
    doc = Doc(tags=["admin", "sessions"], summary="Revoke session by ID")
    query = s.SessionPath
    response = Response(OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                session = await app.dao.sessions.get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Session not found") from None

            # ADMIN не выбивает владельца из его же админки
            if app.current_admin.role != AdminRole.OWNER:
                grant = await app.get_active_admin_grant(session.identity_id)
                if grant and AdminRole(grant.role) == AdminRole.OWNER:
                    raise Forbidden(message="Only OWNER can revoke sessions of an OWNER")

            # Не app.revoke_session: тот проверяет принадлежность current_identity
            await app.dao.sessions.update_by_id(session.id, status=SessionStatus.REVOKED)
            return {"ok": True}
