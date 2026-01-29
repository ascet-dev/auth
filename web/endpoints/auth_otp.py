from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

logger = getLogger(__name__)


class SendOtp(JsonEndpoint):
    doc = Doc(tags=["auth", "otp"], summary="Send OTP code")

    # body = s.SendOtpRequest  # TODO
    # response = Response(s.OtpChallengeResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # challenge = await app.auth.send_otp(
        #     destination=ctx.body.destination,
        #     channel=ctx.body.channel,
        # )
        # return challenge

        return {"todo": "send otp"}


class LoginByOtp(JsonEndpoint):
    doc = Doc(tags=["auth", "otp"], summary="Login by OTP")

    # body = s.LoginByOtpRequest  # TODO
    # response = Response(s.SessionWithTokens)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # session, tokens = await app.auth.login_by_otp(
        #     challenge_id=ctx.body.challenge_id,
        #     code=ctx.body.code,
        # )
        # return {
        #     "session": session,
        #     "access_token": tokens[0],
        #     "refresh_token": tokens[1],
        # }

        return {"todo": "login by otp"}
