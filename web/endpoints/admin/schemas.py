"""
Схемы admin CRUD API.

Read-модели выводятся из табличных моделей через `.exclude()` / `.only()`
(adc_aiopg Base), чтобы не дублировать поля руками: секреты отсекаются
на уровне модели ответа, а не только сериализацией.
Search-модели наследуют `BaseSearch` из models/base.py.
"""

import copy
from typing import Any
from uuid import UUID

from adc_aiopg.types import Base
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, create_model

from models.admin_grant import AuthAdminGrant
from models.base import BaseSearch
from models.client_app import ClientApp
from models.connector import AuthConnector
from models.credential import Credential
from models.enums import AdminRole, AuthMethod, IdentityStatus, SessionStatus
from models.identity import AuthIdentity
from models.identity_external_link import AuthIdentityExternalLink
from models.logins import Login
from models.session import Session


def optional(model: type[Base], name: str) -> type[Base]:
    """
    Все поля модели становятся необязательными (для PATCH-схем).

    Своя реализация вместо Base.partial(): та мутирует FieldInfo исходной модели
    (объекты полей общие), из-за чего у родителя пропадали бы обязательные поля.
    """
    fields: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        clone = copy.deepcopy(field)
        clone.default = None
        fields[field_name] = (field.annotation | None, clone)
    return create_model(name, __base__=Base, **fields)


# ---------------------------------------------------------------- запросы

PAGE_LIMIT_MAX = 200

# Path-схемы выводятся из моделей: видно, id какой сущности ждём,
# и изменение типа PK подтянется само
ClientAppPath = ClientApp.only("id")
ConnectorPath = AuthConnector.only("id")
IdentityPath = AuthIdentity.only("id")
SessionPath = Session.only("id")
GrantPath = AuthAdminGrant.only("id")


class AdminSearch(BaseSearch):
    """BaseSearch с потолком страницы: админка ходит в API из браузера."""

    limit: int = Field(50, ge=1, le=PAGE_LIMIT_MAX)
    offset: int = Field(0, ge=0)


class ClientAppSearch(AdminSearch):
    key: str | None = None


class ConnectorSearch(AdminSearch):
    type: AuthMethod | None = None
    enabled: bool | None = None


class IdentitySearch(AdminSearch):
    status: IdentityStatus | None = None
    tenant_id: str | None = None


class GrantSearch(AdminSearch):
    identity_id: UUID | None = None
    role: AdminRole | None = None


class SessionSearch(AdminSearch):
    # Сессии живут по status, а не по archived
    archived: bool | None = None
    identity_id: UUID | None = None
    client_app_id: UUID | None = None
    status: SessionStatus | None = None


class LoginSearch(AdminSearch):
    # Аудит append-only, archived не используется
    archived: bool | None = None
    identity_id: UUID | None = None
    identifier: str | None = None
    method: str | None = None
    success: bool | None = None


# ---------------------------------------------------------------- read-модели

ClientAppRead = ClientApp
IdentityRead = AuthIdentity
GrantRead = AuthAdminGrant
LoginRead = Login
ExternalLinkRead = AuthIdentityExternalLink

# Хэш refresh-токена наружу не отдаём
SessionRead = Session.exclude("refresh_token_hash")

# Секреты в settings маскируются при сериализации (см. connectors.py):
# в JSONB-поле их заменяют флаги <key>_set
ConnectorRead = AuthConnector

# Ни секретов, ни счётчиков блокировки — только то, что нужно карточке identity
CredentialSummary = Credential.only(
    "id",
    "type",
    "identifier",
    "provider",
    "external_subject_id",
    "last_used",
)


class IdentityDetail(PydanticBaseModel):
    identity: IdentityRead
    credentials: list[CredentialSummary]
    external_links: list[ExternalLinkRead]
    grant: GrantRead | None = None


# ---------------------------------------------------------------- write-модели


# Create/Update выводятся из модели: набор и типы полей едут за ней,
# руками задаётся только то, чего в модели нет (что редактируемо, что immutable)
ClientAppCreate = ClientApp.only(
    "key",
    "name",
    "type",
    "allowed_redirect_uris",
    "allowed_scopes",
    "access_token_ttl_sec",
    "refresh_token_ttl_sec",
)
# key immutable — это идентификатор аудитории
ClientAppUpdate = optional(ClientAppCreate.exclude("key"), "ClientAppUpdate")


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


class GrantCreate(PydanticBaseModel):
    identity_id: UUID
    role: AdminRole = AdminRole.ADMIN
