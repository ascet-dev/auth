from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING
from uuid import UUID

from adc_aiopg.types import Paginated
from adc_webkit.errors import BadRequest, Unauthorized
from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

import models as m
from web.auth import jwt

from . import schemas as s

logger = getLogger(__name__)

if TYPE_CHECKING:
    from services import App


class RefreshSession(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Refresh session (rotate refresh token)")

    body = s.RefreshSessionRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        try:
            session, tokens = await app.refresh_session(
                refresh_token=ctx.body.refresh_token,
                client_app_id=ctx.body.client_app_id,
            )
        except ValueError as e:
            msg = str(e) or "Invalid refresh token"
            if "invalid refresh token" in msg.lower() or "expired" in msg.lower():
                raise Unauthorized(message=msg) from e
            raise BadRequest(message=msg) from e

        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }


class Logout(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Revoke current session")
    auth = jwt

    body = s.RevokeSessionRequest
    response = Response(s.OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        identity_id: UUID = ctx.auth_payload.sub
        async with app.request_scope({"current_identity": {"sub": identity_id, "dao": app.dao}}):
            await app.revoke_session(ctx.body.session_id)
            return {"ok": True}


class ListSessions(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="List all active sessions for identity")
    auth = jwt

    response = Response(Paginated[m.Session])

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        identity_id: UUID = ctx.auth_payload.sub
        async with app.request_scope(
            {
                "current_identity": {"sub": identity_id, "dao": app.dao},
            },
        ):
            sessions = await app.list_sessions()
            return sessions


class RevokeSession(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Revoke specific session by ID")
    auth = jwt

    response = Response(s.OkResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        identity_id: UUID = ctx.auth_payload.sub

        # Получаем session_id из пути (path parameter)
        session_id_str = ctx.request.path_params.get("session_id")
        if not session_id_str:
            raise ValueError("session_id is required")

        session_id = UUID(session_id_str)

        async with app.request_scope({"current_identity": {"sub": identity_id, "dao": app.dao}}):
            # Проверяем, что сессия принадлежит текущему пользователю
            session = await app.dao.sessions.get_by_id(session_id)
            if not session:
                raise ValueError("Session not found")

            if session.identity_id != identity_id:
                raise ValueError("Session does not belong to current user")

            await app.revoke_session(session_id)
            return {"ok": True}


class RevokeAllSessions(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Revoke all sessions for identity")
    auth = jwt

    response = Response(s.RevokedSessionsResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        identity_id: UUID = ctx.auth_payload.sub

        async with app.request_scope({"current_identity": {"sub": identity_id, "dao": app.dao}}):
            revoked_sessions = await app.revoke_all_sessions(identity_id)
            return {"revoked_sessions": revoked_sessions}
