from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from adc_appkit.components.component import Component

from models.enums import IdentityStatus
from models.identity import AuthIdentity

if TYPE_CHECKING:
    from uuid import UUID

    from services.repositories import DAO

logger = getLogger(__name__)


class CurrentIdentity(Component[AuthIdentity]):
    """
    REQUEST-scoped компонент для получения и валидации текущего пользователя.

    Извлекает identity_id из контекста запроса (ctx["identity_id"]),
    загружает identity из БД и валидирует, что она активна.

    Использование:
        В App:
            current_identity = component(
                CurrentIdentity,
                strategy=ComponentStrategy.REQUEST,
                config_key="current_identity",
                dependencies={"dao": "dao"}
            )

        В RequestScope контексте:
            identity = app.current_identity  # автоматически валидированный AuthIdentity
    """

    async def _start(self, sub: UUID, dao: DAO) -> AuthIdentity:
        """
        Загружает и валидирует identity.

        Args:
            identity_id: UUID identity из контекста запроса
            dao: DAO для доступа к БД

        Returns:
            AuthIdentity - валидированная identity

        Raises:
            ValueError: Если identity не найдена или не активна
        """
        logger.debug("Loading identity: %s", sub)

        identity = await dao.identities.get_by_id(sub)

        if not identity:
            raise ValueError(f"Identity {sub} not found")

        if identity.status != IdentityStatus.ACTIVE:
            raise ValueError(f"Identity {sub} is not active (status: {identity.status})")

        logger.debug("Identity loaded and validated: %s", sub)
        return identity

    async def _stop(self) -> None:
        """Очистка при выходе из request scope."""

    async def is_alive(self) -> bool:
        """Проверка, что identity все еще активна."""
        # В request scope identity не меняется, поэтому всегда True
        return True
