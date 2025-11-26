from uuid import UUID

from sqlmodel import Field

from .base import BaseModel


class Login(BaseModel):
    method: str = Field(description="Метод входа: 'password', 'otp', 'oauth' и т.д.")

    identifier: str | None = Field(
        default=None,
        description="Идентификатор для входа (email, phone, username и т.д.)",
    )

    identity_id: UUID | None = Field(
        default=None,
        foreign_key="auth_identities.id",
        description="Может быть NULL, если попытка входа неуспешна и identity не найдена",
    )

    credential_id: UUID | None = Field(
        default=None,
        foreign_key="auth_credentials.id",
        description="Credential, через который была попытка входа",
    )

    success: bool = Field(description="Успешна ли попытка входа")

    ip_address: str = Field(description="IP адрес клиента")

    user_agent: str = Field(description="User-Agent клиента")
