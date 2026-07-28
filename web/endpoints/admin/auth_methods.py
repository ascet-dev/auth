from __future__ import annotations

from typing import TYPE_CHECKING, Any

from adc_webkit.web import Ctx, Response
from adc_webkit.web.openapi import Doc

from models.enums import AuthMethod
from services.service import AUTH_METHOD_DEFAULTS
from settings import cfg

from . import schemas as s
from .base import AdminEndpoint

if TYPE_CHECKING:
    from models.auth_method import AuthMethodSetting
    from services import App


def _method_view(method: AuthMethod, row: AuthMethodSetting | None) -> dict[str, Any]:
    defaults = AUTH_METHOD_DEFAULTS[method]
    settings = {**defaults["settings"], **((row.settings if row else None) or {})}
    return {
        "method": method,
        "enabled": row.enabled if row else defaults["enabled"],
        "configured": row is not None,
        "allow_registration": settings.get("allow_registration") if method == AuthMethod.PASSWORD else None,
        "bot_token_set": bool(settings.get("bot_token")) if method == AuthMethod.TMA else False,
        "env_bot_token_set": bool(cfg.auth.telegram_bot_token) if method == AuthMethod.TMA else False,
        "auth_date_max_age": settings.get("auth_date_max_age") if method == AuthMethod.TMA else None,
    }


async def _get_row(app: App, method: AuthMethod) -> AuthMethodSetting | None:
    rows = await app.dao.auth_methods.search(method=method, archived=False, limit=1)
    return rows[0] if rows else None


class AdminListAuthMethods(AdminEndpoint):
    doc = Doc(tags=["admin", "auth-methods"], summary="Auth methods config (global toggles + params)")

    response = Response(list[s.AuthMethodRead])

    async def execute(self, ctx: Ctx) -> list:  # type: ignore[override, unused-ignore]
        async with self.admin_scope(ctx) as app:
            return [_method_view(method, await _get_row(app, method)) for method in AuthMethod]


class AdminUpdateAuthMethod(AdminEndpoint):
    doc = Doc(tags=["admin", "auth-methods"], summary="Update auth method (upsert)")

    query = s.ByMethodPath
    body = s.AuthMethodUpdate
    response = Response(s.AuthMethodRead)

    async def execute(self, ctx: Ctx) -> dict:
        async with self.admin_scope(ctx) as app:
            method: AuthMethod = ctx.query.method
            row = await _get_row(app, method)

            defaults = AUTH_METHOD_DEFAULTS[method]
            enabled = (
                ctx.body.enabled if ctx.body.enabled is not None else (row.enabled if row else defaults["enabled"])
            )

            settings = dict((row.settings if row else None) or {})
            patch = ctx.body.model_dump(exclude_unset=True, exclude={"enabled"})
            if method == AuthMethod.PASSWORD and "allow_registration" in patch:
                settings["allow_registration"] = patch["allow_registration"]
            if method == AuthMethod.TMA:
                if patch.get("bot_token") is not None:
                    # пустая строка = очистить (fallback на env)
                    settings["bot_token"] = patch["bot_token"] or None
                if "auth_date_max_age" in patch and patch["auth_date_max_age"] is not None:
                    settings["auth_date_max_age"] = patch["auth_date_max_age"]

            if row:
                row = await app.dao.auth_methods.update_by_id(row.id, enabled=enabled, settings=settings)
            else:
                row = await app.dao.auth_methods.create(method=method, enabled=enabled, settings=settings)

            return _method_view(method, row)
