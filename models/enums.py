from enum import Enum


class IdentityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DELETED = "DELETED"


class CredentialType(str, Enum):
    PASSWORD = "PASSWORD"  # noqa: S105
    OTP_PHONE = "OTP_PHONE"
    OTP_EMAIL = "OTP_EMAIL"
    OAUTH = "OAUTH"
    API_KEY = "API_KEY"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    COMPROMISED = "COMPROMISED"


class OtpChannel(str, Enum):
    SMS = "SMS"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"


class AuthClientType(str, Enum):
    PUBLIC = "PUBLIC"
    CONFIDENTIAL = "CONFIDENTIAL"
