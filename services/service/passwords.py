"""Пароли: регистрация, проверка credential с lockout, логин."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from models.credential import Credential  # noqa: TC001
from models.enums import AuthMethod, CredentialType, IdentityStatus
from models.identity import AuthIdentity  # noqa: TC001
from models.session import Session  # noqa: TC001
from services.service.constants import LOCKOUT_DURATION_MINUTES, MAX_FAILED_ATTEMPTS

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class PasswordsMixin(ServiceBase):
    async def register_password_identity(
        self,
        identifier: str,
        password: str,
        client_app_id: UUID | None = None,
    ) -> AuthIdentity:
        """
        Создаёт новую identity + password credential.
        identifier — email, phone, username и т.п.
        НЕ привязывает к существующим identities.
        """
        _, policy = await self.resolve_auth_connector(AuthMethod.PASSWORD, client_app_id)
        if not policy.get("allow_registration", True):
            raise ValueError("Registration is disabled")

        existing = await self.dao.credentials.search(
            identifier=identifier,
            type=CredentialType.PASSWORD,
            archived=False,
            limit=1,
        )
        if existing:
            raise ValueError("Credential with this identifier already exists")

        identity = await self.dao.identities.create(
            status=IdentityStatus.ACTIVE,
        )

        secret_hash = self.password_service.hash_password(password)
        await self.dao.credentials.create(
            identity_id=identity.id,
            type=CredentialType.PASSWORD,
            identifier=identifier,
            secret_hash=secret_hash,
            failed_attempts=0,
        )

        return identity

    async def _verify_password_credential(
        self,
        identifier: str,
        password: str,
        *,
        max_failed_attempts: int = MAX_FAILED_ATTEMPTS,
        lockout_minutes: int = LOCKOUT_DURATION_MINUTES,
    ) -> Credential:
        """
        Находит password credential по identifier и проверяет пароль:
        lockout, счётчики неудачных попыток, сброс счётчиков при успехе.
        Политика (лимиты) приходит из password-коннектора приложения.
        """
        now = datetime.datetime.now(datetime.UTC)

        credentials = await self.dao.credentials.search(
            identifier=identifier,
            type=CredentialType.PASSWORD,
            archived=False,
            limit=1,
        )

        if not credentials:
            raise ValueError("Invalid credentials")  # todo 400
        credential = credentials[0]

        if credential.locked_until and credential.locked_until > now:
            # Тот же ответ, что и на неверный пароль: иначе состояние блокировки
            # выдаёт существование учётки (enumeration) и порог политики.
            raise ValueError("Invalid credentials")

        if not credential.secret_hash or not self.password_service.verify_password(
            password,
            credential.secret_hash,
        ):
            # Инкремент считает БД: read-modify-write в Python позволял обойти
            # lockout параллельными запросами (все читали одно и то же значение).
            table = self.dao.credentials.model
            # Истёкшая блокировка обнуляет счётчик, иначе одна попытка после
            # каждого окна держала бы учётку залоченной бессрочно.
            lock_expired = sa.and_(table.locked_until.isnot(None), table.locked_until <= now)
            next_attempts = sa.case((lock_expired, 1), else_=table.failed_attempts + 1)
            await self.dao.credentials.update_by_id(
                credential.id,
                failed_attempts=next_attempts,
                locked_until=sa.case(
                    (
                        next_attempts >= max_failed_attempts,
                        now + datetime.timedelta(minutes=lockout_minutes),
                    ),
                    (lock_expired, None),
                    else_=table.locked_until,
                ),
            )
            # Ответ на неверный пароль всегда одинаковый; блокировка сработает
            # на следующей попытке (проверка locked_until выше).
            raise ValueError("Invalid credentials")

        credential.failed_attempts = 0
        credential.locked_until = None
        credential.last_used = now
        await self.dao.credentials.update_by_id(
            credential.id,
            failed_attempts=0,
            locked_until=None,
            last_used=now,
        )

        return credential

    async def login_by_password(
        self,
        identifier: str,
        password: str,
        client_app_id: UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Находит credential по type=password и identifier.
        Проверяет пароль.
        Создаёт новую сессию.
        """
        async with self.log_login_attempt(
            method="password",
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            await self.ensure_public_client_app(client_app_id)
            _, policy = await self.resolve_auth_connector(AuthMethod.PASSWORD, client_app_id)

            credential = await self._verify_password_credential(
                identifier,
                password,
                max_failed_attempts=policy["max_failed_attempts"],
                lockout_minutes=policy["lockout_minutes"],
            )

            session, tokens = await self.create_session(
                credential.identity_id,
                client_app_id,
                ip=ip_address,
                user_agent=user_agent,
            )

            # Устанавливаем identity_id и credential_id для успешного логирования
            logger.set(identity_id=credential.identity_id, credential_id=credential.id)

            return session, tokens
