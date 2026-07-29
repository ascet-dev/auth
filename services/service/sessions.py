"""Сессии: создание, refresh, ревокация."""

from __future__ import annotations

import datetime
import hashlib
from typing import TYPE_CHECKING

from adc_aiopg import RowNotFoundError

from models.client_app import ClientApp  # noqa: TC001
from models.enums import SessionStatus
from models.session import Session  # noqa: TC001
from services.service.errors import AdminGrantRevokedError, IdentityInactiveError

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID

    from adc_aiopg.types import Paginated


class SessionsMixin(ServiceBase):
    async def _get_active_client_app(self, client_app_id: UUID) -> ClientApp:
        """client_app, пригодный для выдачи сессий: архивация должна отключать вход."""
        try:
            client_app = await self.dao.client_apps.get_by_id(client_app_id)
        except RowNotFoundError:
            raise ValueError("Client app not found") from None
        if client_app.archived:
            raise ValueError("Client app is archived")
        return client_app

    async def create_session(
        self,
        identity_id: UUID,
        client_app_id: UUID,
        **session_data: object,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Создаёт новую сессию:
        - генерирует access_token и refresh_token
        - хэширует refresh_token
        - сохраняет session
        - возвращает (session, (access, refresh))
        """
        # Получаем client_app для получения TTL
        client_app = await self._get_active_client_app(client_app_id)

        # Генерируем токены
        access_token = await self.generate_access_token(identity_id, client_app_id)
        refresh_token = await self.generate_refresh_token()

        # Хэшируем refresh_token
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Вычисляем время истечения refresh_token
        refresh_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=client_app.refresh_token_ttl_sec,
        )

        # Сохраняем сессию
        session = await self.dao.sessions.create(
            identity_id=identity_id,
            client_app_id=client_app_id,
            refresh_token_hash=refresh_token_hash,
            refresh_expires_at=refresh_expires_at,
            status=SessionStatus.ACTIVE,
            **session_data,
        )

        return session, (access_token, refresh_token)

    async def refresh_session(
        self,
        refresh_token: str,
        client_app_id: UUID,
    ) -> tuple[Session, tuple[str, str]]:
        """
        1. Находит сессию по hash(refresh_token)
        2. Проверяет срок
        3. Делает rotation refresh-токена
        4. Генерирует новый access
        """
        now = datetime.datetime.now(datetime.UTC)

        # 1) find session by refresh hash
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        sessions = await self.dao.sessions.search(
            refresh_token_hash=refresh_token_hash,
            status=SessionStatus.ACTIVE,
            limit=1,
        )
        if not sessions:
            raise ValueError("Invalid refresh token")

        session = sessions[0]

        # 2) validate client app and expiry
        if session.client_app_id != client_app_id:
            raise ValueError("Refresh token client mismatch")

        if session.refresh_expires_at <= now:
            await self.dao.sessions.update_by_id(session.id, status=SessionStatus.EXPIRED)
            raise ValueError("Refresh token expired")

        client_app = await self._get_active_client_app(client_app_id)

        # 3) rotate refresh token (new opaque token + hash)
        new_refresh_token = await self.generate_refresh_token()
        new_refresh_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        new_refresh_expires_at = now + datetime.timedelta(seconds=client_app.refresh_token_ttl_sec)

        await self.dao.sessions.update_by_id(
            session.id,
            refresh_token_hash=new_refresh_hash,
            refresh_expires_at=new_refresh_expires_at,
            last_used_at=now,
        )

        # 4) new access token
        try:
            access_token = await self.generate_access_token(session.identity_id, client_app_id)
        except (AdminGrantRevokedError, IdentityInactiveError):
            # Грант отозван или identity заблокирована — сессия больше не имеет права жить
            await self.dao.sessions.update_by_id(session.id, status=SessionStatus.REVOKED)
            raise ValueError("Invalid refresh token") from None

        session = await self.dao.sessions.get_by_id(session.id)
        return session, (access_token, new_refresh_token)

    async def revoke_session(self, session_id: UUID) -> Session:
        """
        Помечает сессию как revoked.
        """
        session = await self.dao.sessions.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")

        if session.identity_id != self.current_identity.id:
            raise ValueError("Session does not belong to current user")

        await self.dao.sessions.update_by_id(
            session_id,
            status=SessionStatus.REVOKED,
        )
        return session

    async def revoke_all_sessions(self, identity_id: UUID) -> int:
        """
        Отзывает все сессии пользователя.
        """

        # Отзываем все сессии пользователя
        updated_sessions = await self.dao.sessions.update(
            {"status": SessionStatus.REVOKED},
            identity_id=identity_id,
            status=SessionStatus.ACTIVE,
        )
        return len(updated_sessions)

    async def list_sessions(self) -> Paginated[Session]:
        """
        Возвращает все активные/незавершённые сессии identity.
        """
        # Получаем все активные сессии (не отозванные и не истёкшие)
        now = datetime.datetime.now(datetime.UTC)

        sessions = await self.dao.sessions.paginated_search(
            identity_id=self.current_identity.id,
            status=SessionStatus.ACTIVE,
            refresh_expires_at_gt=now,
        )

        return sessions
