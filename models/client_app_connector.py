from uuid import UUID

from sqlalchemy import Index, text
from sqlmodel import Field

from models.base import BaseModel


class AuthClientAppConnector(BaseModel):
    """
    Привязка коннектора к приложению (M2M).

    Нет ни одной активной привязки у приложения = разрешены все включённые
    коннекторы. Уникальность пары — partial unique index (archived = false).
    """

    # Индексы объявлены в модели, иначе следующий autogenerate снесёт их из БД
    __table_args__ = (
        Index(
            "uq_auth_client_app_connectors_pair",
            "client_app_id",
            "connector_id",
            unique=True,
            postgresql_where=text("archived = false"),
        ),
    )

    client_app_id: UUID = Field(foreign_key="auth_client_apps.id")
    connector_id: UUID = Field(foreign_key="auth_connectors.id")
