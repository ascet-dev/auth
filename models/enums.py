from enum import Enum

from models.base import meta


class IdentityStatus(str, Enum):
    __meta__ = meta

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DELETED = "DELETED"


class CredentialType(str, Enum):
    __meta__ = meta

    PASSWORD = "PASSWORD"  # noqa: S105
    OTP_PHONE = "OTP_PHONE"
    OTP_EMAIL = "OTP_EMAIL"
    OAUTH = "OAUTH"
    API_KEY = "API_KEY"
    TMA = "TMA"


class SessionStatus(str, Enum):
    __meta__ = meta

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    COMPROMISED = "COMPROMISED"


class OtpChannel(str, Enum):
    __meta__ = meta

    SMS = "SMS"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"


class AuthClientType(str, Enum):
    __meta__ = meta

    PUBLIC = "PUBLIC"
    CONFIDENTIAL = "CONFIDENTIAL"
