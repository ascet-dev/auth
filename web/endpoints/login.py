from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s

logger = getLogger(__name__)


class LoginByPassword(JsonEndpoint):
    doc = Doc(tags=["login"], summary="login by password")

    response = Response(s.SessionWithTokens)
    body = s.LoginByPasswordRequest

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        # TODO: use app.login_by_password or redirect to /auth/login/password
        return {"status": "ok"}
