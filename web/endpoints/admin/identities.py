from __future__ import annotations

from adc_aiopg import RowNotFoundError
from adc_aiopg.types import Paginated
from adc_webkit.errors import NotFound
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from . import schemas as s
from .base import AdminEndpoint, AdminList, dump_entity


class AdminListIdentities(AdminList):
    doc = Doc(tags=["admin", "identities"], summary="List identities")
    table = "identities"
    query = s.IdentitySearch
    response = Response(Paginated[s.IdentityRead])


class AdminGetIdentity(AdminEndpoint):
    doc = Doc(tags=["admin", "identities"], summary="Identity detail: credentials, links, grant")
    query = s.ByIdPath
    response = Response(s.IdentityDetail)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            try:
                identity = await app.dao.identities.get_by_id(ctx.query.id)
            except RowNotFoundError:
                raise NotFound(message="Identity not found") from None

            credentials = await app.dao.credentials.search(identity_id=identity.id, archived=False)
            links = await app.dao.identity_external_links.search(identity_id=identity.id, archived=False)
            grant = await app.get_active_admin_grant(identity.id)

            return {
                "identity": dump_entity(identity),
                # dump_entity сохраняет только поля read-модели: хеши отсекает CredentialSummary
                "credentials": [dump_entity(c) for c in credentials],
                "external_links": [dump_entity(link) for link in links],
                "grant": dump_entity(grant) if grant else None,
            }
