from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

from adc_aiopg import RowNotFoundError
from adc_appkit.components.component import Component

from models.admin_grant import AuthAdminGrant  # noqa: TC001
from models.enums import AdminRole, IdentityStatus
from models.identity import AuthIdentity  # noqa: TC001

if TYPE_CHECKING:
    from uuid import UUID

    from services.repositories import DAO

logger = getLogger(__name__)


@dataclass
class AdminContext:
    identity: AuthIdentity
    grant: AuthAdminGrant

    @property
    def role(self) -> AdminRole:
        return AdminRole(self.grant.role)


class CurrentAdmin(Component[AdminContext]):
    """
    REQUEST-scoped компонент для получения и валидации текущего админа.

    Помимо валидности JWT проверяет по БД, что identity активна и грант
    не отозван — отзыв прав действует сразу, не дожидаясь истечения токена.
    """

    async def _start(self, sub: UUID | None = None, dao: DAO | None = None) -> AdminContext | None:
        # RequestScope стартует ВСЕ REQUEST-компоненты: без ctx-конфига — «пустой» старт
        if sub is None or dao is None:
            return None

        logger.debug("Loading admin identity: %s", sub)

        try:
            identity = await dao.identities.get_by_id(sub)
        except RowNotFoundError:
            raise ValueError(f"Identity {sub} not found") from None

        if identity.status != IdentityStatus.ACTIVE:
            raise ValueError(f"Identity {sub} is not active (status: {identity.status})")

        grants = await dao.admin_grants.search(identity_id=sub, archived=False, limit=1)
        if not grants:
            raise ValueError(f"Identity {sub} has no active admin grant")

        return AdminContext(identity=identity, grant=grants[0])

    async def _stop(self) -> None:
        """Очистка при выходе из request scope."""

    async def is_alive(self) -> bool:
        return True
