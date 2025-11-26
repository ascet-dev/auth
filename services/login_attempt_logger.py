from __future__ import annotations

from uuid import UUID

from models.logins import Login
from services.repositories import DAO


class LoginAttemptLogger:
    """Контекстный менеджер для логирования попыток входа."""

    def __init__(
        self,
        dao: DAO,
        method: str,
        identifier: str | None,
        ip_address: str,
        user_agent: str,
    ):
        self.dao = dao
        self.method = method
        self.identifier = identifier
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.identity_id: UUID | None = None
        self.credential_id: UUID | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        await self.dao.logins.create(
            method=self.method,
            identifier=self.identifier,
            identity_id=self.identity_id,
            credential_id=self.credential_id,
            success=success,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
        )

        # Не подавляем исключения - пробрасываем дальше
        return False

    def set(self, *, identity_id: UUID | None = None, credential_id: UUID | None = None):
        """
        Устанавливает identity_id и/или credential_id для логирования.

        Args:
            identity_id: ID identity для успешного логирования
            credential_id: ID credential для логирования
        """
        if identity_id is not None:
            self.identity_id = identity_id
        if credential_id is not None:
            self.credential_id = credential_id
