from adc_aiopg import RowNotFoundError
from adc_aiopg.types import Paginated
from adc_webkit.errors import NotFound
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from models.enums import SessionStatus
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
    query = s.ByIdPath
    response = Response(OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                # Не app.revoke_session: тот проверяет принадлежность current_identity
                await app.dao.sessions.update_by_id(ctx.query.id, status=SessionStatus.REVOKED)
            except RowNotFoundError:
                raise NotFound(message="Session not found") from None
            return {"ok": True}
