from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from . import schemas as s

logger = getLogger(__name__)

if TYPE_CHECKING:
    from services import App


class StartOauthFlow(JsonEndpoint):
    doc = Doc(tags=["auth", "oauth"], summary="Start OAuth flow")

    body = s.StartOAuthRequest
    response = Response(s.StartOAuthResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        redirect_url = await app.start_oauth_flow(
            provider=ctx.body.provider,
            redirect_uri=ctx.body.redirect_uri,
        )
        return {"redirect_url": redirect_url}


class LoginByOauth(JsonEndpoint):
    doc = Doc(tags=["auth", "oauth"], summary="Login by OAuth callback")

    body = s.LoginByOAuthRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # Получаем IP и User-Agent из запроса
        ip_address = ctx.request.client.host if ctx.request.client else None
        user_agent = ctx.request.headers.get("user-agent")

        session, tokens = await app.login_by_oauth(
            provider=ctx.body.provider,
            code=ctx.body.code,
            redirect_uri=ctx.body.redirect_uri,
            client_app_id=ctx.body.client_app_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }
