from enum import Enum


class IdentityStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class CredentialType(str, Enum):
    PASSWORD = "password"  # noqa: S105
    OTP_PHONE = "otp_phone"
    OTP_EMAIL = "otp_email"
    OAUTH = "oauth"
    API_KEY = "api_key"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    COMPROMISED = "compromised"


class OtpChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class AuthClientType(str, Enum):
    PUBLIC = "public"
    CONFIDENTIAL = "confidential"
