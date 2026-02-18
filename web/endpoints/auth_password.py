from logging import getLogger

from adc_webkit.errors import BadRequest, Unauthorized
from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO: определить схемы

logger = getLogger(__name__)


class RegisterPassword(JsonEndpoint):
    doc = Doc(tags=["auth", "password"], summary="Register new identity with password")

    body = s.RegisterPasswordRequest
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        try:
            identity = await app.register_password_identity(
                identifier=ctx.body.login,
                password=ctx.body.password,
            )
        except ValueError as e:
            raise BadRequest(message=str(e)) from e

        return {"identity_id": str(identity.id), "status": identity.status}


class LoginByPassword(JsonEndpoint):
    doc = Doc(tags=["auth", "password"], summary="Login by password")

    body = s.LoginByPasswordRequest
    response = Response(s.SessionWithTokens)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # Получаем IP и User-Agent из запроса
        ip_address = ctx.request.client.host if ctx.request.client else None
        user_agent = ctx.request.headers.get("user-agent")

        try:
            session, tokens = await app.login_by_password(
                identifier=ctx.body.login,
                password=ctx.body.password,
                client_app_id=ctx.body.client_app_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except ValueError as e:
            msg = str(e) or "Invalid credentials"
            # минимальная нормализация ошибок: не отдаём 500 на ожидаемые кейсы
            # todo: сделать обработку стандартных ошибок в вьюхе или мидлвари
            if "invalid credentials" in msg.lower():
                raise Unauthorized(message=msg) from e
            raise BadRequest(message=msg) from e

        return {
            "session": session.model_dump(exclude={"refresh_token_hash"}),
            "access_token": tokens[0],
            "refresh_token": tokens[1],
        }
