from uuid import UUID

from adc_aiopg.enum import sqla_enum
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AdminRole


class AuthAdminGrant(BaseModel):
    """
    Явная выдача админских прав на identity.

    Уникальность активного гранта обеспечивается partial unique index
    (identity_id) WHERE archived = false — после отзыва грант можно выдать повторно.
    """

    identity_id: UUID = Field(foreign_key="auth_identities.id")

    role: AdminRole = Field(default=AdminRole.ADMIN, sa_column=sqla_enum(AdminRole).sa_column)

    # NULL = bootstrap (грант выдан при инициализации сервиса)
    granted_by: UUID | None = Field(default=None, foreign_key="auth_identities.id")
