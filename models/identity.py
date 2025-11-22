from sqlmodel import Field

from models.base import BaseModel
from models.enums import IdentityStatus


class AuthIdentity(BaseModel):
    __tablename__ = "auth_identities"

    tenant_id: str | None = Field(default=None)

    status: IdentityStatus = Field(default=IdentityStatus.ACTIVE)
