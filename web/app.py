from adc_webkit.web import Web
from adc_webkit.web.web import Route

from services import App
from settings import cfg
from web import endpoints as e

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
    ]


web = WebApp.create(bindings={"app": app})
