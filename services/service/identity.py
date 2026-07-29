"""Identity и внешние маппинги."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.identity import AuthIdentity  # noqa: TC001

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class IdentityMixin(ServiceBase):
    async def create_identity(self, *, tenant_id: str | None = None) -> AuthIdentity:
        """
        Создаёт новую пустую identity без credential.
        """
        raise NotImplementedError()

    async def get_identity(self, identity_id: UUID) -> AuthIdentity:
        """Получает identity по ID."""
        return await self.dao.identities.get_by_id(identity_id)

    async def delete_identity(self, identity_id: UUID) -> None:
        """
        Мягкое удаление identity (status = deleted).
        """
        raise NotImplementedError()

    # External links

    async def link_external_user(self, identity_id: UUID, external_system: str, external_user_id: str) -> None:
        """
        Добавляет маппинг identity -> внешний пользователь (например фингуляр user_id).
        Нужен для дедупликации на стороне внешнего сервиса.
        """
        raise NotImplementedError()
