from uuid import UUID

from adc_aiopg.enum import sqla_enum
from sqlalchemy import Index, text
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AdminRole


class AuthAdminGrant(BaseModel):
    """
    Явная выдача админских прав на identity.

    Уникальность активного гранта обеспечивается partial unique index
    (identity_id) WHERE archived = false — после отзыва грант можно выдать повторно.
    """

    # Индексы объявлены в модели, иначе следующий autogenerate снесёт их из БД
    __table_args__ = (
        Index(
            "uq_auth_admin_grants_identity_active",
            "identity_id",
            unique=True,
            postgresql_where=text("archived = false"),
        ),
    )

    identity_id: UUID = Field(foreign_key="auth_identities.id")

    role: AdminRole = Field(default=AdminRole.ADMIN, sa_column=sqla_enum(AdminRole).sa_column)

    # NULL = bootstrap (грант выдан при инициализации сервиса)
    granted_by: UUID | None = Field(default=None, foreign_key="auth_identities.id")
