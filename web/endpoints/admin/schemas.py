"""Схемы admin CRUD API. Read-модели явные — секреты не покидают сервис."""

from datetime import datetime
from uuid import UUID

from adc_aiopg.types import Base
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from models.enums import AdminRole, AuthClientType, AuthMethod, CredentialType, IdentityStatus, SessionStatus

# ---------------------------------------------------------------- запросы


class ByIdPath(PydanticBaseModel):
    id: UUID


class AdminSearch(PydanticBaseModel):
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    archived: bool = False


class ClientAppSearch(AdminSearch):
    pass


class ConnectorSearch(AdminSearch):
    type: AuthMethod | None = None
    enabled: bool | None = None


class IdentitySearch(AdminSearch):
    status: IdentityStatus | None = None
    tenant_id: str | None = None


class GrantSearch(AdminSearch):
    identity_id: UUID | None = None
    role: AdminRole | None = None


class SessionSearch(PydanticBaseModel):
    # Сессии фильтруются по status, а не archived
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    identity_id: UUID | None = None
    client_app_id: UUID | None = None
    status: SessionStatus | None = None


class LoginSearch(PydanticBaseModel):
    # Аудит append-only, archived не используется
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    identity_id: UUID | None = None
    identifier: str | None = None
    method: str | None = None
    success: bool | None = None
    created_ge: datetime | None = None
    created_le: datetime | None = None


# ---------------------------------------------------------------- read-модели


class BaseRead(Base):
    # Наследует adc_aiopg Base: элементы Paginated[B] должны быть его подтипом
    id: UUID
    created: datetime | None = None
    updated: datetime | None = None
    archived: bool | None = None


class ClientAppRead(BaseRead):
    key: str
    name: str
    type: AuthClientType | None = None
    allowed_redirect_uris: list[str] | None = None
    allowed_scopes: list[str] | None = None
    access_token_ttl_sec: int
    refresh_token_ttl_sec: int


class ConnectorRead(BaseRead):
    key: str
    type: AuthMethod
    name: str
    enabled: bool
    # Секреты (bot_token, client_secret) заменены на флаги <key>_set
    settings: dict = {}


class IdentityRead(BaseRead):
    tenant_id: str | None = None
    status: IdentityStatus | None = None


class SessionRead(BaseRead):
    identity_id: UUID
    client_app_id: UUID
    refresh_expires_at: datetime
    status: SessionStatus | None = None
    last_used_at: datetime | None = None
    ip: str | None = None
    user_agent: str | None = None
    device_id: str | None = None


class LoginRead(BaseRead):
    method: str
    identifier: str | None = None
    identity_id: UUID | None = None
    credential_id: UUID | None = None
    success: bool
    ip_address: str | None = None
    user_agent: str | None = None


class GrantRead(BaseRead):
    identity_id: UUID
    role: AdminRole
    granted_by: UUID | None = None


class CredentialSummary(PydanticBaseModel):
    id: UUID
    type: CredentialType | None = None
    identifier: str | None = None
    provider: str | None = None
    external_subject_id: str | None = None
    last_used: datetime | None = None


class ExternalLinkRead(BaseRead):
    identity_id: UUID
    external_system: str
    external_user_id: str


class IdentityDetail(PydanticBaseModel):
    identity: IdentityRead
    credentials: list[CredentialSummary]
    external_links: list[ExternalLinkRead]
    grant: GrantRead | None = None


# ---------------------------------------------------------------- write-модели


class ClientAppCreate(PydanticBaseModel):
    key: str
    name: str
    type: AuthClientType = AuthClientType.PUBLIC
    allowed_redirect_uris: list[str] = []
    allowed_scopes: list[str] = []
    access_token_ttl_sec: int = 900
    refresh_token_ttl_sec: int = 60 * 60 * 24 * 30


class ClientAppUpdate(PydanticBaseModel):
    # key immutable — идентификатор аудитории
    name: str | None = None
    type: AuthClientType | None = None
    allowed_redirect_uris: list[str] | None = None
    allowed_scopes: list[str] | None = None
    access_token_ttl_sec: int | None = None
    refresh_token_ttl_sec: int | None = None


class OauthProviderCreate(PydanticBaseModel):
    name: str
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    jwks_url: str | None = None
    userinfo_url: str | None = None
    enabled: bool = True


class OauthProviderUpdate(PydanticBaseModel):
    name: str | None = None
    client_id: str | None = None
    # None / отсутствие поля = не менять секрет
    client_secret: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    jwks_url: str | None = None
    userinfo_url: str | None = None
    enabled: bool | None = None


class GrantCreate(PydanticBaseModel):
    identity_id: UUID
    role: AdminRole = AdminRole.ADMIN


# ---------------------------------------------------------------- коннекторы


# Типизированные settings по типу коннектора: без валидации в JSONB попадали
# строки вместо чисел ("3") и ломали сравнения в login-флоу уже в рантайме.


class PasswordSettings(PydanticBaseModel):
    model_config = {"extra": "forbid"}

    max_failed_attempts: int | None = Field(default=None, ge=1, le=100)
    lockout_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 7)
    allow_registration: bool | None = None


class TmaSettings(PydanticBaseModel):
    model_config = {"extra": "forbid"}

    # "" при обновлении = очистить (fallback на env), None = не менять
    bot_token: str | None = None
    auth_date_max_age: int | None = Field(default=None, ge=10, le=60 * 60 * 24)


class OauthSettings(PydanticBaseModel):
    model_config = {"extra": "forbid"}

    client_id: str | None = Field(default=None, min_length=1)
    client_secret: str | None = None
    auth_url: str | None = Field(default=None, min_length=1)
    token_url: str | None = Field(default=None, min_length=1)
    jwks_url: str | None = None
    userinfo_url: str | None = None


class OtpSettings(PydanticBaseModel):
    model_config = {"extra": "forbid"}


CONNECTOR_SETTINGS_MODELS: dict[AuthMethod, type[PydanticBaseModel]] = {
    AuthMethod.PASSWORD: PasswordSettings,
    AuthMethod.TMA: TmaSettings,
    AuthMethod.OAUTH: OauthSettings,
    AuthMethod.OTP: OtpSettings,
}


class ConnectorCreate(PydanticBaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    type: AuthMethod
    name: str = Field(min_length=1)
    enabled: bool = True
    # Валидируется по type в эндпоинте (CONNECTOR_SETTINGS_MODELS)
    settings: dict = {}


class ConnectorUpdate(PydanticBaseModel):
    # key и type immutable
    name: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    # merge по ключам; секрет: отсутствие/None = не менять, "" = очистить
    settings: dict | None = None


class ClientAppConnectorsUpdate(PydanticBaseModel):
    connector_ids: list[UUID]
