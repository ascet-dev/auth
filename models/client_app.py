from sqlmodel import Field

from models.base import BaseModel
from models.enums import AuthClientType


class ClientApp(BaseModel):
    __tablename__ = "auth_client_apps"

    # логический идентификатор клиента/аудитории
    key: str = Field(description="Например 'finqular-web', 'finqular-api', 'stronica-web'")
    name: str

    type: AuthClientType = Field(default=AuthClientType.PUBLIC)

    allowed_redirect_uris: list[str] = Field(default_factory=list)
    allowed_scopes: list[str] = Field(default_factory=list)

    access_token_ttl_sec: int = Field(default=900)
    refresh_token_ttl_sec: int = Field(default=60 * 60 * 24 * 30)  # 30 дней
