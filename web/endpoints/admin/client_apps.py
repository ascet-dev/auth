from adc_aiopg.types import Paginated
from adc_webkit.web import Response
from adc_webkit.web.openapi import Doc

from web.endpoints.schemas import OkResponse

from . import schemas as s
from .base import AdminArchive, AdminCreate, AdminGet, AdminList, AdminUpdate


class AdminListClientApps(AdminList):
    doc = Doc(tags=["admin", "client-apps"], summary="List client apps")
    table = "client_apps"
    query = s.ClientAppSearch
    response = Response(Paginated[s.ClientAppRead])


class AdminGetClientApp(AdminGet):
    doc = Doc(tags=["admin", "client-apps"], summary="Get client app")
    table = "client_apps"
    query = s.ByIdPath
    response = Response(s.ClientAppRead)


class AdminCreateClientApp(AdminCreate):
    doc = Doc(tags=["admin", "client-apps"], summary="Create client app")
    table = "client_apps"
    body = s.ClientAppCreate
    response = Response(s.ClientAppRead)


class AdminUpdateClientApp(AdminUpdate):
    doc = Doc(tags=["admin", "client-apps"], summary="Update client app (key immutable)")
    table = "client_apps"
    query = s.ByIdPath
    body = s.ClientAppUpdate
    response = Response(s.ClientAppRead)


class AdminArchiveClientApp(AdminArchive):
    doc = Doc(tags=["admin", "client-apps"], summary="Archive client app (soft delete)")
    table = "client_apps"
    query = s.ByIdPath
    response = Response(OkResponse)
