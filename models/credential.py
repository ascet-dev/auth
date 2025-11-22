import typing as t
from datetime import datetime
from uuid import UUID

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from models.base import BaseModel
from models.enums import CredentialType


class Credential(BaseModel):
    __tablename__ = "auth_credentials"

    identity_id: UUID = Field(foreign_key="auth_identities.id")

    type: CredentialType = Field(default=CredentialType.PASSWORD)

    # чем идентифицируем логин: email / phone / username и т.п.
    identifier: str | None = Field(
        default=None,
        description="email/phone/username и т.п. в зависимости от типа credential",
    )

    # для OAUTH / внешних провайдеров
    provider: str | None = Field(
        default=None,
        description="Например 'google', 'apple', 'github'",
    )

    # hash пароля / api-key / другого секрета (не для одноразовых OTP)
    secret_hash: str | None = Field(default=None)

    # для OAuth: subject/id от провайдера
    external_subject_id: str | None = Field(default=None)

    meta: dict[str, t.Any] | None = Field(default_factory=dict, sa_column=Column(JSONB))

    failed_attempts: int = Field(default=0)
    locked_until: datetime | None = Field(default=None)

    last_used: datetime | None = Field(default=None)
