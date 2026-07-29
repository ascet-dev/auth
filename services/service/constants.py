"""Константы бизнес-логики."""

from models.enums import AuthMethod

# Парольная политика по умолчанию (переопределяется settings PASSWORD-коннектора)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

HTTP_OK = 200

# Системный client_app для сессий админов auth-сервиса
AUTH_ADMIN_CLIENT_KEY = "auth-admin"
AUTH_ADMIN_REFRESH_TTL_SEC = 60 * 60 * 24 * 7  # 7 дней

# Дефолтные настройки по типу коннектора: подмешиваются под settings коннектора.
# Если коннекторов типа нет вообще — PASSWORD/TMA работают на встроенных дефолтах
# (TMA — при заданном env-токене), существующие инсталляции ничего не настраивают.
CONNECTOR_DEFAULTS: dict[AuthMethod, dict] = {
    AuthMethod.PASSWORD: {
        "max_failed_attempts": MAX_FAILED_ATTEMPTS,
        "lockout_minutes": LOCKOUT_DURATION_MINUTES,
        "allow_registration": True,
    },
    AuthMethod.OTP: {},
    AuthMethod.TMA: {},
    AuthMethod.OAUTH: {},
}
