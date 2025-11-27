from adc_aiopg.enum import sqla_enum
from sqlmodel import Field

from models.base import BaseModel
from models.enums import IdentityStatus


class AuthIdentity(BaseModel):
    tenant_id: str | None = Field(default=None)

    status: IdentityStatus = Field(default=IdentityStatus.ACTIVE, sa_column=sqla_enum(IdentityStatus).sa_column)
