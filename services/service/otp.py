"""OTP (не реализовано)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.enums import AuthMethod
from models.otp_challenge import AuthOtpChallenge  # noqa: TC001
from models.session import Session  # noqa: TC001

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class OtpMixin(ServiceBase):
    async def send_otp(self, destination: str, channel: str) -> AuthOtpChallenge:  # noqa: ARG002
        """
        1. Создаёт OTP challenge
        2. Генерирует код
        3. Сохраняет hash
        4. Отправляет через внешний сервис уведомлений
        """
        await self.resolve_auth_connector(AuthMethod.OTP)
        raise NotImplementedError()

    async def login_by_otp(self, challenge_id: UUID, code: str) -> tuple[Session, tuple[str, str]]:  # noqa: ARG002
        """
        1. Проверяет OTP challenge
        2. Находит или создаёт identity
        3. Создаёт OTP credential (если надо)
        4. Создаёт новую сессию
        """
        await self.resolve_auth_connector(AuthMethod.OTP)
        raise NotImplementedError()
