"""Коннекторы: резолв способа входа для приложения."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.connector import AuthConnector  # noqa: TC001
from models.enums import AuthMethod
from services.service.constants import CONNECTOR_DEFAULTS
from settings import cfg

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class ConnectorsMixin(ServiceBase):
    async def list_app_connector_ids(self, client_app_id: UUID) -> set[UUID] | None:
        """ID коннекторов, привязанных к приложению. None = привязок нет (все разрешены)."""
        links = await self.dao.client_app_connectors.search(client_app_id=client_app_id, archived=False)
        return {link.connector_id for link in links} if links else None

    async def resolve_auth_connector(
        self,
        method: AuthMethod,
        client_app_id: UUID | None = None,
        key: str | None = None,
    ) -> tuple[str, dict]:
        """
        Резолвит коннектор для login-флоу: тип + приложение (+ явный key от клиента).
        Возвращает (connector_key, effective_settings).

        Правила:
        - привязки приложения (M2M) — whitelist; нет привязок = все включённые;
        - key задан → берём его из доступных;
        - ровно один доступный → он; несколько → нужен явный key;
        - коннекторов типа нет вообще и whitelist не задан → встроенный дефолт
          (PASSWORD: политика из констант; TMA: env bot token).

        Админ-логин (login_by_admin) резолвер НЕ использует — чтобы нельзя было
        отрезать себе доступ к админке, выключив пароль.
        """
        method_key = method.value.lower()
        all_of_type: list[AuthConnector] = await self.dao.connectors.search(type=method, archived=False)
        enabled_of_type = [c for c in all_of_type if c.enabled]

        whitelist: set[UUID] | None = None
        if client_app_id:
            whitelist = await self.list_app_connector_ids(client_app_id)

        allowed = enabled_of_type if whitelist is None else [c for c in enabled_of_type if c.id in whitelist]

        def effective(connector: AuthConnector) -> tuple[str, dict]:
            return connector.key, {**CONNECTOR_DEFAULTS[method], **(connector.settings or {})}

        if key:
            for connector in allowed:
                if connector.key == key:
                    return effective(connector)
            raise ValueError(f"Auth connector '{key}' is not available for this application")

        if len(allowed) == 1:
            return effective(allowed[0])
        if len(allowed) > 1:
            raise ValueError(f"Multiple '{method_key}' connectors available, specify connector")

        # доступных нет
        if whitelist is not None:
            raise ValueError(f"Auth method '{method_key}' is not allowed for this application")
        if all_of_type:
            raise ValueError(f"Auth method '{method_key}' is disabled")

        # коннекторов типа не существует → встроенные дефолты
        if method == AuthMethod.PASSWORD:
            return "password", dict(CONNECTOR_DEFAULTS[AuthMethod.PASSWORD])
        if method == AuthMethod.TMA and cfg.auth.telegram_bot_token:
            return "tma", {
                "bot_token": cfg.auth.telegram_bot_token,
                "auth_date_max_age": cfg.auth.tma_auth_date_max_age,
            }
        raise ValueError(f"Auth method '{method_key}' is not configured")
