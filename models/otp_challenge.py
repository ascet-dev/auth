import typing as t
from datetime import datetime
from uuid import UUID

from sqlmodel import Field

from models.base import BaseModel
from models.enums import OtpChannel


class AuthOtpChallenge(BaseModel):
    __tablename__ = "auth_otp_challenges"

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

    meta: dict[str, t.Any] | None = Field(default_factory=dict)
