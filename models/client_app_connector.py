from uuid import UUID

from sqlmodel import Field

from models.base import BaseModel


class AuthClientAppConnector(BaseModel):
    """
    Привязка коннектора к приложению (M2M).

    Нет ни одной активной привязки у приложения = разрешены все включённые
    коннекторы. Уникальность пары — partial unique index (archived = false).
    """

    client_app_id: UUID = Field(foreign_key="auth_client_apps.id")
    connector_id: UUID = Field(foreign_key="auth_connectors.id")
