from logging import getLogger

from adc_webkit.web import Ctx, JsonEndpoint, Response
from adc_webkit.web.openapi import Doc

from services import App

from . import schemas as s  # TODO

logger = getLogger(__name__)


class RefreshSession(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Refresh session (rotate refresh token)")

    # body = s.RefreshSessionRequest  # TODO
    # response = Response(s.SessionWithTokens)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # session, tokens = await app.auth.refresh_session(
        #     refresh_token=ctx.body.refresh_token,
        #     client_app_id=ctx.body.client_app_id,
        # )
        # return {
        #     "session": session,
        #     "access_token": tokens[0],
        #     "refresh_token": tokens[1],
        # }

        return {"todo": "refresh session"}


class Logout(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Revoke current session")

    # body = s.LogoutRequest  # TODO
    # response = Response(s.OkResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # await app.auth.revoke_session(ctx.body.session_id)

        return {"todo": "logout"}


class ListSessions(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="List all active sessions for identity")

    # query = s.ListSessionsQuery  # TODO
    # response = Response(s.SessionsListResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # sessions = await app.auth.list_sessions(identity_id=ctx.query.identity_id)
        # return {"sessions": sessions}

        return {"todo": "list sessions"}


class RevokeAllSessions(JsonEndpoint):
    doc = Doc(tags=["auth", "sessions"], summary="Revoke all sessions for identity")

    # body = s.RevokeAllSessionsRequest  # TODO
    # response = Response(s.OkResponse)  # TODO
    response = Response(dict)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app

        # TODO:
        # await app.auth.revoke_all_sessions(identity_id=ctx.body.identity_id)

        return {"todo": "revoke all sessions"}
