from datetime import datetime
from uuid import UUID

from adc_aiopg.enum import sqla_enum
from sqlmodel import Field

from models.base import BaseModel
from models.enums import SessionStatus


class Session(BaseModel):
    identity_id: UUID = Field(foreign_key="auth_identities.id")

    client_app_id: UUID = Field(
        foreign_key="auth_client_apps.id",
    )

    refresh_token_hash: str = Field(description="Хэш refresh-токена (сам токен хранится у клиента)")
    refresh_expires_at: datetime

    status: SessionStatus = sqla_enum(SessionStatus, default=SessionStatus.ACTIVE)

    last_used_at: datetime | None = Field(default=None)

    ip: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    device_id: str | None = Field(default=None)

    # device_info: dict[str, t.Any] | None = Field(default_factory=dict)
