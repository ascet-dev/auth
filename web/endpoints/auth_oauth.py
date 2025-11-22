from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO

logger = getLogger(__name__)


class StartOauthFlow(JsonEndpoint):
    doc = Doc(tags=["auth", "oauth"], summary="Start OAuth flow")

    # body = s.StartOAuthRequest  # TODO
    # response = Response(s.StartOAuthResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # redirect_url = await app.auth.start_oauth_flow(
        #     provider=ctx.body.provider,
        #     redirect_uri=ctx.body.redirect_uri,
        # )
        # return {"redirect_url": redirect_url}

        return {"todo": "start oauth flow"}


class LoginByOauth(JsonEndpoint):
    doc = Doc(tags=["auth", "oauth"], summary="Login by OAuth callback")

    # body = s.LoginByOAuthRequest  # TODO
    # response = Response(s.SessionWithTokens)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # session, tokens = await app.auth.login_by_oauth(
        #     provider=ctx.body.provider,
        #     code=ctx.body.code,
        #     redirect_uri=ctx.body.redirect_uri,
        # )
        # return {
        #     "session": session,
        #     "access_token": tokens[0],
        #     "refresh_token": tokens[1],
        # }

        return {"todo": "login by oauth"}
