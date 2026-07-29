"""Управление credential-ами (не реализовано)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.credential import Credential  # noqa: TC001

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class CredentialsMixin(ServiceBase):
    async def link_password_to_identity(self, identity_id: UUID, password: str) -> Credential:
        """
        Добавляет password credential существующей identity.
        """
        raise NotImplementedError()

    async def link_otp_to_identity(self, identity_id: UUID, destination: str, channel: str) -> Credential:
        """
        Привязывает телефон/email как способ входа для существующей identity.
        """
        raise NotImplementedError()

    async def revoke_credential(self, credential_id: UUID) -> None:
        """
        Архивирует/отзывает credential.
        """
        raise NotImplementedError()
