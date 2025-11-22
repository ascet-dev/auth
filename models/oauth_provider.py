from sqlmodel import Field

from models.base import BaseModel


class AuthOauthProvider(BaseModel, table=True):
    __tablename__ = "auth_oauth_providers"

    name: str = Field(description="Системное имя провайдера: 'google', 'apple', 'vk', 'github'")

    client_id: str
    client_secret: str

    auth_url: str
    token_url: str
    jwks_url: str | None = Field(default=None)
    userinfo_url: str | None = Field(default=None)

    # scopes: list[str] = Field(default_factory=list)

    enabled: bool = Field(default=True)
