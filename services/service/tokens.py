"""Сборка и подпись JWT."""

from __future__ import annotations

import datetime
import secrets
from typing import TYPE_CHECKING

from adc_aiopg import RowNotFoundError
from jose import jwt

from models.enums import IdentityStatus
from services.service.constants import AUTH_ADMIN_CLIENT_KEY
from services.service.errors import AdminGrantRevokedError, IdentityInactiveError
from settings import cfg

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class TokensMixin(ServiceBase):
    async def build_jwt_payload(
        self,
        identity_id: UUID,
        client_app_id: UUID,
    ) -> dict:
        """
        1. Основные claims: sub, iat, exp, tenant
        2. Для системного client_app `auth-admin` добавляет claim `role`
        3. Дёргает внешний сервис за бизнес-контекстом

        Единая точка выдачи access-токенов, поэтому статус identity проверяется
        здесь: BLOCKED/DELETED не должен получить подписанный токен ни при
        логине, ни при refresh (внешние потребители проверяют только подпись).
        """
        try:
            identity = await self.dao.identities.get_by_id(identity_id)
        except RowNotFoundError:
            raise IdentityInactiveError(f"Identity {identity_id} not found") from None

        if identity.status != IdentityStatus.ACTIVE:
            raise IdentityInactiveError(f"Identity is not active (status: {identity.status})")

        now = datetime.datetime.now(datetime.UTC)
        exp = now + cfg.auth.access_token_lifetime

        payload = {
            "sub": str(identity_id),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "type": "access",
        }

        if identity.tenant_id:
            payload["tenant"] = identity.tenant_id

        client_app = await self.dao.client_apps.get_by_id(client_app_id)
        if client_app.key == AUTH_ADMIN_CLIENT_KEY:
            grant = await self.get_active_admin_grant(identity_id)
            if not grant:
                # Грант отозван: refresh_session по этой ошибке ревокает сессию
                raise AdminGrantRevokedError("Admin grant is revoked")
            payload["role"] = str(grant.role)

        # TODO: Дёргать внешний сервис за бизнес-контекстом
        # payload.update(await external_service.get_claims(identity_id))

        return payload

    async def generate_access_token(self, identity_id: UUID, client_app_id: UUID) -> str:
        """
        Создаёт короткоживущий access JWT.
        """
        payload = await self.build_jwt_payload(identity_id, client_app_id)
        return jwt.encode(payload, cfg.auth.private_key, algorithm=cfg.auth.algorithms[0])

    async def generate_refresh_token(self) -> str:
        """
        Генерирует длинный opaque token для сессии.
        """
        # Генерируем криптографически стойкий случайный токен
        return secrets.token_urlsafe(64)
