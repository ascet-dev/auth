from typing import Any

from adc_aiopg.types import Paginated
from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminArchive, AdminCreate, AdminGet, AdminList, AdminUpdate, dump_entity


def serialize_provider(entity: Any) -> dict:
    """client_secret write-only: наружу отдаём только client_secret_set."""
    data = dump_entity(entity)
    data.pop("client_secret", None)
    data["client_secret_set"] = bool(entity.client_secret)
    return data


class AdminListOauthProviders(AdminList):
    doc = Doc(tags=["admin", "oauth-providers"], summary="List OAuth providers")
    table = "oauth_providers"
    query = s.OauthProviderSearch
    response = Response(Paginated[s.OauthProviderRead])

    def serialize(self, entity: Any) -> dict:
        return serialize_provider(entity)


class AdminGetOauthProvider(AdminGet):
    doc = Doc(tags=["admin", "oauth-providers"], summary="Get OAuth provider")
    table = "oauth_providers"
    query = s.ByIdPath
    response = Response(s.OauthProviderRead)

    def serialize(self, entity: Any) -> dict:
        return serialize_provider(entity)


class AdminCreateOauthProvider(AdminCreate):
    doc = Doc(tags=["admin", "oauth-providers"], summary="Create OAuth provider")
    table = "oauth_providers"
    body = s.OauthProviderCreate
    response = Response(s.OauthProviderRead)

    def serialize(self, entity: Any) -> dict:
        return serialize_provider(entity)


class AdminUpdateOauthProvider(AdminUpdate):
    doc = Doc(tags=["admin", "oauth-providers"], summary="Update OAuth provider (secret: None = keep)")
    table = "oauth_providers"
    query = s.ByIdPath
    body = s.OauthProviderUpdate
    response = Response(s.OauthProviderRead)

    def serialize(self, entity: Any) -> dict:
        return serialize_provider(entity)

    def build_update_payload(self, ctx: Ctx) -> dict:
        payload = ctx.body.model_dump(exclude_unset=True)
        # None = «не менять секрет», а не «стереть»
        if payload.get("client_secret") is None:
            payload.pop("client_secret", None)
        return payload


class AdminArchiveOauthProvider(AdminArchive):
    doc = Doc(tags=["admin", "oauth-providers"], summary="Archive OAuth provider (soft delete)")
    table = "oauth_providers"
    query = s.ByIdPath
    response = Response(OkResponse)
