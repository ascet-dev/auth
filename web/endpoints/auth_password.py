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

    # body = s.LoginByPasswordRequest  # TODO
    # response = Response(s.SessionWithTokens)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # session, tokens = await app.login_by_password(
        #     identifier=ctx.body.identifier,
        #     password=ctx.body.password,
        # )
        # return {
        #     "session": session,
        #     "access_token": tokens[0],
        #     "refresh_token": tokens[1],
        # }

        return {"todo": "login by password"}
