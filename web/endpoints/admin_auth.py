from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from adc_webkit.errors import BadRequest, Unauthorized
from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from web.auth import admin_jwt

from . import schemas as s

logger = getLogger(__name__)

if TYPE_CHECKING:
    from services import App


class AdminLogin(JsonEndpoint):
    doc = Doc(tags=["admin"], summary="Admin login (password + admin grant)")

    body = s.AdminLoginRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        ip_address = ctx.request.client.host if ctx.request.client else None
        user_agent = ctx.request.headers.get("user-agent")

        try:
            session, tokens = await app.login_by_admin(
                identifier=ctx.body.login,
                password=ctx.body.password,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except ValueError as e:
            msg = str(e) or "Invalid credentials"
            if "invalid credentials" in msg.lower():
                raise Unauthorized(message=msg) from e
            raise BadRequest(message=msg) from e

        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }


class AdminRefreshSession(JsonEndpoint):
    doc = Doc(tags=["admin"], summary="Refresh admin session (rotate refresh token)")

    body = s.AdminRefreshRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        try:
            client_app = await app.get_admin_client_app()
            session, tokens = await app.refresh_session(
                refresh_token=ctx.body.refresh_token,
                client_app_id=client_app.id,
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


class AdminMe(JsonEndpoint):
    doc = Doc(tags=["admin"], summary="Current admin identity and role")
    auth = admin_jwt

    response = Response(s.AdminMeResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        try:
            async with app.request_scope({"current_admin": {"sub": ctx.auth_payload.sub, "dao": app.dao}}):
                admin = app.current_admin
                return {"identity_id": admin.identity.id, "role": str(admin.role)}
        except ValueError as e:
            # identity не активна или грант отозван — токен больше не годится
            raise Unauthorized(message=str(e)) from e
