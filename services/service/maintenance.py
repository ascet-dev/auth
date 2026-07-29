"""Фоновые чистки."""

from __future__ import annotations

from .base import ServiceBase


class MaintenanceMixin(ServiceBase):
    async def cleanup_expired_sessions(self) -> int:
        """
        Удаляет / архивирует истёкшие сессии.
        Возвращает число обработанных.
        """
        raise NotImplementedError()

    async def cleanup_expired_otp(self) -> int:
        """
        Чистит старые OTP-вызовы.
        """
        raise NotImplementedError()
