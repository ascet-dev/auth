from adc_aiopg.types import Paginated
from adc_webkit.web import Response
from adc_webkit.web.openapi import Doc

from . import schemas as s
from .base import AdminList


class AdminListLogins(AdminList):
    doc = Doc(tags=["admin", "logins"], summary="Login audit log")
    table = "logins"
    query = s.LoginSearch
    response = Response(Paginated[s.LoginRead])
