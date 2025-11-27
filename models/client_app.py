from adc_aiopg.enum import sqla_enum
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AuthClientType


class ClientApp(BaseModel):
    # логический идентификатор клиента/аудитории
    key: str = Field(description="Например 'finqular-web', 'finqular-api', 'stronica-web'")
    name: str

    type: AuthClientType = Field(default=AuthClientType.PUBLIC, sa_column=sqla_enum(AuthClientType).sa_column)

    allowed_redirect_uris: list[str] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
    )
    allowed_scopes: list[str] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
    )

    access_token_ttl_sec: int = Field(default=900)
    refresh_token_ttl_sec: int = Field(default=60 * 60 * 24 * 30)  # 30 дней
