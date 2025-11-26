from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO: определить схемы

logger = getLogger(__name__)


class RegisterPassword(JsonEndpoint):
    doc = Doc(tags=["auth", "password"], summary="Register new identity with password")

    # body = s.RegisterPasswordRequest  # TODO
    # response = Response(s.IdentityResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # identity = await app.register_password_identity(
        #     email=ctx.body.email,
        #     password=ctx.body.password,
        # )
        # return identity

        return {"todo": "register password"}


class LoginByPassword(JsonEndpoint):
    doc = Doc(tags=["auth", "password"], summary="Login by password")

    body = s.LoginByPasswordRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # Получаем IP и User-Agent из запроса
        ip_address = ctx.request.client.host if ctx.request.client else None
        user_agent = ctx.request.headers.get("user-agent")

        session, tokens = await app.login_by_password(
            identifier=ctx.body.login,
            password=ctx.body.password,
            client_app_id=ctx.body.client_app_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }
