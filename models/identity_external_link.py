from uuid import UUID

from sqlmodel import Field

from models.base import BaseModel


class AuthIdentityExternalLink(BaseModel):
    __tablename__ = "auth_identity_external_links"

    identity_id: UUID = Field(foreign_key="auth_identities.id")

    external_system: str = Field(description="Имя внешней системы, например 'finqular-core', 'stronica-core'")
    external_user_id: str = Field(description="ID пользователя во внешней системе")
    # уникальность по (identity_id, external_system, external_user_id)
    # можно задать через миграцию/алембик
