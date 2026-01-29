from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

logger = getLogger(__name__)


class CleanupSessions(JsonEndpoint):
    doc = Doc(tags=["auth", "maintenance"], summary="Clean expired sessions")

    # response = Response(s.CleanupResult)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # n = await app.auth.cleanup_expired_sessions()
        # return {"processed": n}

        return {"todo": "cleanup sessions"}


class CleanupOtp(JsonEndpoint):
    doc = Doc(tags=["auth", "maintenance"], summary="Clean expired OTP challenges")

    # response = Response(s.CleanupResult)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # n = await app.auth.cleanup_expired_otp()
        # return {"processed": n}

        return {"todo": "cleanup otp"}
