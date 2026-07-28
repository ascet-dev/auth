from pathlib import Path

from adc_webkit.web import Web
from adc_webkit.web.web import Route
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from services import App
from settings import cfg
from web import endpoints as e
from web.endpoints import admin as ea

app = App(
    components_config={
        "pg": cfg.pg.connection.model_dump(),
        "dao": {},
    },
)


class WebApp(Web):
    cors = cfg.app.cors.model_dump()
    routes = [
        # health
        Route("GET", "/readiness", e.Readiness),
        Route("GET", "/liveness", e.Liveness),
        # password auth
        Route("POST", "/auth/register/password", e.RegisterPassword),
        Route("POST", "/auth/login/password", e.LoginByPassword),
        # OTP
        Route("POST", "/auth/otp/send", e.SendOtp),
        Route("POST", "/auth/otp/login", e.LoginByOtp),
        # OAuth
        Route("POST", "/auth/oauth/start", e.StartOauthFlow),
        Route("POST", "/auth/oauth/login", e.LoginByOauth),
        # TMA (Telegram Mini App)
        Route("POST", "/auth/tma/login", e.LoginByTMA),
        # sessions
        Route("POST", "/auth/session/refresh", e.RefreshSession),
        Route("POST", "/auth/session/logout", e.Logout),
        Route("GET", "/auth/sessions", e.ListSessions),
        Route("DELETE", "/auth/sessions/{session_id}", e.RevokeSession),
        Route("POST", "/auth/sessions/revoke-all", e.RevokeAllSessions),
        # identity
        Route("POST", "/auth/identity", e.CreateIdentity),
        Route("GET", "/auth/identity", e.GetIdentity),
        Route("DELETE", "/auth/identity", e.DeleteIdentity),
        # credentials management
        Route("POST", "/auth/credentials/password/link", e.LinkPassword),
        Route("POST", "/auth/credentials/otp/link", e.LinkOtp),
        Route("POST", "/auth/credentials/oauth/link", e.LinkOauth),
        Route("POST", "/auth/credentials/revoke", e.RevokeCredential),
        # external mapping
        Route("POST", "/auth/external/link", e.LinkExternalUser),
        # maintenance
        Route("POST", "/auth/maintenance/cleanup-sessions", e.CleanupSessions),
        Route("POST", "/auth/maintenance/cleanup-otp", e.CleanupOtp),
        # admin auth
        Route("POST", "/admin/auth/login", e.AdminLogin),
        Route("POST", "/admin/auth/refresh", e.AdminRefreshSession),
        Route("GET", "/admin/auth/me", e.AdminMe),
        # admin: client apps
        Route("GET", "/admin/client-apps", ea.AdminListClientApps),
        Route("POST", "/admin/client-apps", ea.AdminCreateClientApp),
        Route("GET", "/admin/client-apps/{id}", ea.AdminGetClientApp),
        Route("PATCH", "/admin/client-apps/{id}", ea.AdminUpdateClientApp),
        Route("DELETE", "/admin/client-apps/{id}", ea.AdminArchiveClientApp),
        # admin: oauth providers
        Route("GET", "/admin/oauth-providers", ea.AdminListOauthProviders),
        Route("POST", "/admin/oauth-providers", ea.AdminCreateOauthProvider),
        Route("GET", "/admin/oauth-providers/{id}", ea.AdminGetOauthProvider),
        Route("PATCH", "/admin/oauth-providers/{id}", ea.AdminUpdateOauthProvider),
        Route("DELETE", "/admin/oauth-providers/{id}", ea.AdminArchiveOauthProvider),
        # admin: identities (read-only)
        Route("GET", "/admin/identities", ea.AdminListIdentities),
        Route("GET", "/admin/identities/{id}", ea.AdminGetIdentity),
        # admin: sessions
        Route("GET", "/admin/sessions", ea.AdminListSessions),
        Route("DELETE", "/admin/sessions/{id}", ea.AdminRevokeSession),
        # admin: login audit
        Route("GET", "/admin/logins", ea.AdminListLogins),
        # admin: grants (OWNER-only mutations)
        Route("GET", "/admin/grants", ea.AdminListGrants),
        Route("POST", "/admin/grants", ea.AdminCreateGrant),
        Route("DELETE", "/admin/grants/{id}", ea.AdminRevokeGrant),
        # admin: auth methods
        Route("GET", "/admin/auth-methods", ea.AdminListAuthMethods),
        Route("PATCH", "/admin/auth-methods/{method}", ea.AdminUpdateAuthMethod),
    ]


web = WebApp.create(bindings={"app": app})

# Проверка инициализации: web стартует в любом случае (пользовательский auth
# работает независимо), но без OWNER-а пишем ERROR в лог.
web.web.add_event_handler("startup", app.check_owner_initialized)


HTTP_NOT_FOUND = 404


class SPAStaticFiles(StaticFiles):
    """Fallback на index.html для client-side роутинга SPA."""

    async def get_response(self, path: str, scope):  # type: ignore[no-untyped-def]
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == HTTP_NOT_FOUND:
                return await super().get_response("index.html", scope)
            raise


# Админский UI: dist собирается в Docker (stage frontend-build).
# Локально без сборки фронта API просто стартует без UI.
UI_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if UI_DIST.is_dir():
    web.web.mount("/admin/ui", SPAStaticFiles(directory=str(UI_DIST), html=True), name="admin-ui")
    web.web.add_route("/", lambda request: RedirectResponse("/admin/ui/"), methods=["GET"])  # noqa: ARG005
