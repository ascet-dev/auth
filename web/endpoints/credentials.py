from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO

logger = getLogger(__name__)


class LinkPassword(JsonEndpoint):
    doc = Doc(tags=["auth", "credentials"], summary="Link password to identity")

    # body = s.LinkPasswordRequest  # TODO
    # response = Response(s.CredentialResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # cred = await app.link_password_to_identity(
        #     identity_id=ctx.body.identity_id,
        #     password=ctx.body.password,
        # )
        # return cred

        return {"todo": "link password"}


class LinkOtp(JsonEndpoint):
    doc = Doc(tags=["auth", "credentials"], summary="Link OTP channel to identity")

    # body = s.LinkOtpRequest  # TODO
    # response = Response(s.CredentialResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # cred = await app.link_otp_to_identity(
        #     identity_id=ctx.body.identity_id,
        #     destination=ctx.body.destination,
        #     channel=ctx.body.channel,
        # )
        # return cred

        return {"todo": "link otp"}


class LinkOauth(JsonEndpoint):
    doc = Doc(tags=["auth", "credentials"], summary="Link OAuth provider to identity")

    # body = s.LinkOAuthRequest  # TODO
    # response = Response(s.CredentialResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # cred = await app.link_oauth_to_identity(
        #     identity_id=ctx.body.identity_id,
        #     provider=ctx.body.provider,
        #     code=ctx.body.code,
        # )
        # return cred

        return {"todo": "link oauth"}


class RevokeCredential(JsonEndpoint):
    doc = Doc(tags=["auth", "credentials"], summary="Revoke credential")

    # body = s.RevokeCredentialRequest  # TODO
    # response = Response(s.OkResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # await app.revoke_credential(credential_id=ctx.body.credential_id)

        return {"todo": "revoke credential"}
