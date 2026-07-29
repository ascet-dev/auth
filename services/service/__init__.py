"""
Бизнес-логика auth-сервиса.

Внешний контракт не изменился: `from services.service import App` и константы
импортируются как раньше, внутри логика разложена по миксинам.
"""

from .app import App
from .constants import (
    AUTH_ADMIN_CLIENT_KEY,
    AUTH_ADMIN_REFRESH_TTL_SEC,
    CONNECTOR_DEFAULTS,
    HTTP_OK,
    LOCKOUT_DURATION_MINUTES,
    MAX_FAILED_ATTEMPTS,
)
from .errors import AdminGrantRevokedError, IdentityInactiveError

__all__ = [
    "AUTH_ADMIN_CLIENT_KEY",
    "AUTH_ADMIN_REFRESH_TTL_SEC",
    "CONNECTOR_DEFAULTS",
    "HTTP_OK",
    "LOCKOUT_DURATION_MINUTES",
    "MAX_FAILED_ATTEMPTS",
    "AdminGrantRevokedError",
    "App",
    "IdentityInactiveError",
]
