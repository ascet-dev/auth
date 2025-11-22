from logging import getLogger
from uuid import UUID

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO

logger = getLogger(__name__)


class CreateIdentity(JsonEndpoint):
    doc = Doc(tags=["auth", "identity"], summary="Create empty identity")

    # body = s.CreateIdentityRequest  # TODO
    # response = Response(s.IdentityResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # identity = await app.create_identity(tenant_id=ctx.body.tenant_id)
        # return identity

        return {"todo": "create identity"}


class GetIdentity(JsonEndpoint):
    doc = Doc(tags=["auth", "identity"], summary="Get identity by ID")

    # query = s.GetIdentityQuery  # TODO
    # response = Response(s.IdentityResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # identity_id = UUID(ctx.query.identity_id)
        # identity = await app.get_identity(identity_id=identity_id)
        # return identity

        return {"todo": "get identity"}


class DeleteIdentity(JsonEndpoint):
    doc = Doc(tags=["auth", "identity"], summary="Soft delete identity")

    # body = s.DeleteIdentityRequest  # TODO
    # response = Response(s.OkResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # await app.delete_identity(identity_id=ctx.body.identity_id)

        return {"todo": "delete identity"}
