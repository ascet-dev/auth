from adc_aiopg.enum import sqla_enum
from sqlalchemy import Column, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AuthClientType


class ClientApp(BaseModel):
    # Индексы объявлены в модели, иначе следующий autogenerate снесёт их из БД
    __table_args__ = (Index("uq_auth_client_apps_key", "key", unique=True, postgresql_where=text("archived = false")),)

    # логический идентификатор клиента/аудитории
    key: str = Field(description="Например 'finqular-web', 'finqular-api', 'stronica-web'")
    name: str

    type: AuthClientType = Field(default=AuthClientType.PUBLIC, sa_column=sqla_enum(AuthClientType).sa_column)

    # Колонки nullable, поэтому и аннотация optional: read-модели админки
    # выводятся из этой модели и на NULL падали бы валидацией
    allowed_redirect_uris: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
    )
    allowed_scopes: list[str] | None = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
    )

    # Способы входа приложения — M2M auth_client_app_connectors:
    # нет активных привязок = разрешены все включённые коннекторы

    access_token_ttl_sec: int = Field(default=900)
    refresh_token_ttl_sec: int = Field(default=60 * 60 * 24 * 30)  # 30 дней
