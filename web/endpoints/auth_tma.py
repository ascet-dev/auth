from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from adc_webkit.errors import BadRequest, Unauthorized
from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from . import schemas as s

logger = getLogger(__name__)

if TYPE_CHECKING:
    from services import App


class LoginByTMA(JsonEndpoint):
    doc = Doc(tags=["auth", "tma"], summary="Login by Telegram Mini App initData")

    body = s.LoginByTMARequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        ip_address = ctx.request.client.host if ctx.request.client else None
        user_agent = ctx.request.headers.get("user-agent")

        try:
            session, tokens = await app.login_by_tma(
                init_data=ctx.body.init_data,
                client_app_id=ctx.body.client_app_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except ValueError as e:
            msg = str(e) or "Invalid TMA data"
            if "signature" in msg.lower() or "expired" in msg.lower():
                raise Unauthorized(message=msg) from e
            raise BadRequest(message=msg) from e

        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }
