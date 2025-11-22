from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO

logger = getLogger(__name__)


class LinkExternalUser(JsonEndpoint):
    doc = Doc(tags=["auth", "external"], summary="Link identity to external business user")

    # body = s.LinkExternalUserRequest  # TODO
    # response = Response(s.OkResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # await app.auth.link_external_user(
        #     identity_id=ctx.body.identity_id,
        #     external_system=ctx.body.external_system,
        #     external_user_id=ctx.body.external_user_id,
        # )

        return {"todo": "link external user"}
