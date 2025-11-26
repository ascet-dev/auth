from __future__ import annotations

import typing as t
from datetime import datetime
from uuid import UUID

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from models.base import BaseModel
from models.enums import OtpChannel


class AuthOtpChallenge(BaseModel):
    identity_id: UUID | None = Field(
        default=None,
        foreign_key="auth_identities.id",
        description="Может быть NULL, если identity ещё не создана",
    )

    channel: OtpChannel
    destination: str = Field(description="Телефон или email, на который отправлен код")

    code_hash: str = Field(description="Хэш OTP-кода")
    expires_at: datetime

    consumed_at: datetime | None = Field(default=None)
    failed_attempts: int = Field(default=0)

    meta: dict[str, t.Any] | None = Field(
        default=None,
        sa_column=Column(JSONB),
    )
