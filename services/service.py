from __future__ import annotations

import datetime
import hashlib
import secrets
from typing import Optional
from uuid import UUID

from adc_appkit import BaseApp, ComponentStrategy, component
from adc_appkit.components.component import create_component
from adc_appkit.components.pg import PG
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import and_
from sqlmodel import select

from models.client_app import ClientApp
from models.credential import Credential
from models.enums import CredentialType, SessionStatus
from models.identity import AuthIdentity
from models.otp_challenge import AuthOtpChallenge
from models.session import Session
from services.login_attempt_logger import LoginAttemptLogger
from services.password_service import PasswordService
from services.repositories import DAO
from settings import cfg

# Constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


class App(BaseApp):
    """
    Универсальный сервис аутентификации, который:
    - управляет identities, credentials и sessions;
    - работает с OTP, паролями, OAuth провайдерами;
    - ничего не знает о бизнес-логике внешних систем;
    - получает дополнительные claims для JWT из внешнего сервиса;
    - НЕ делает автолинковки credential → identity.
    """

    pg = component(PG, config_key="pg")
    dao: DAO = component(create_component(DAO), dependencies={"pool": "pg"}, config_key="dao")
    password_service: PasswordService = PasswordService()

    # =============================================================
    # Контекстные менеджеры
    # =============================================================

    def log_login_attempt(
        self,
        method: str,
        identifier: str | None = None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Контекстный менеджер для логирования попыток входа.

        Логирует как успешные, так и неудачные попытки входа.

        Args:
            method: Название метода входа ('password', 'otp', 'oauth')
            identifier: Идентификатор для входа (email, phone, username и т.д.)
            ip_address: IP адрес клиента
            user_agent: User-Agent клиента

        Usage:
            async with app.log_login_attempt(method='password', identifier=identifier, ip_address=ip, user_agent=ua):
                # код входа
                session, tokens = await self.create_session(...)
                return session, tokens
        """
        return LoginAttemptLogger(
            dao=self.dao,
            method=method,
            identifier=identifier,
            ip_address=ip_address or "",
            user_agent=user_agent or "",
        )

    # =============================================================
    # Пароли
    # =============================================================

    async def register_password_identity(self, email: str, password: str) -> AuthIdentity:
        """
        Создаёт новую identity + password credential.
        НЕ привязывает к существующим identities.
        """
        pass

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
            now = datetime.datetime.now(datetime.UTC)

            credential = await self.dao.credentials.search(
                identifier=identifier,
                type=CredentialType.PASSWORD,
                archived=False,
                limit=1,
            )

            if not credential:
                raise ValueError("Invalid credentials")  # todo 400
            credential = credential[0]

            if credential.locked_until and credential.locked_until > now:
                raise ValueError("Credential is locked")

            if not credential.secret_hash or not self.password_service.verify_password(
                password, credential.secret_hash
            ):
                credential.failed_attempts += 1
                if credential.failed_attempts >= MAX_FAILED_ATTEMPTS:
                    credential.locked_until = now + datetime.timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                await self.dao.credentials.update_by_id(
                    credential.id,
                    failed_attempts=credential.failed_attempts,
                    locked_until=credential.locked_until,
                )
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

            session, tokens = await self.create_session(
                credential.identity_id,
                client_app_id,
                ip=ip_address,
                user_agent=user_agent,
            )

            # Устанавливаем identity_id и credential_id для успешного логирования
            logger.set(identity_id=credential.identity_id, credential_id=credential.id)

            return session, tokens

    # =============================================================
    # OTP
    # =============================================================

    async def send_otp(self, destination: str, channel: str) -> AuthOtpChallenge:
        """
        1. Создаёт OTP challenge
        2. Генерирует код
        3. Сохраняет hash
        4. Отправляет через внешний сервис уведомлений
        """
        pass

    async def login_by_otp(self, challenge_id: UUID, code: str) -> tuple[Session, tuple[str, str]]:
        """
        1. Проверяет OTP challenge
        2. Находит или создаёт identity
        3. Создаёт OTP credential (если надо)
        4. Создаёт новую сессию
        """
        pass

    # =============================================================
    # OAuth
    # =============================================================

    async def start_oauth_flow(self, provider: str, redirect_uri: str) -> str:
        """
        Возвращает URL для начала авторизации у провайдера.
        """
        pass

    async def login_by_oauth(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
    ) -> tuple[Session, tuple[str, str]]:
        """
        1. Обменивает code на токен провайдера
        2. Валидирует id_token / profile
        3. Ищет credential по (provider, external_subject_id)
        4. Если нет — создаёт новую identity
        5. Создаёт oauth credential
        6. Создаёт новую сессию
        """
        pass

    async def link_oauth_to_identity(self, identity_id: UUID, provider: str, code: str) -> Credential:
        """
        Явная привязка нового OAuth способа входа к существующей identity.
        Разрешена только из доверенной зоны.
        Автолинковки НЕТ.
        """
        pass

    # =============================================================
    # Credentials
    # =============================================================

    async def link_password_to_identity(self, identity_id: UUID, password: str) -> Credential:
        """
        Добавляет password credential существующей identity.
        """
        pass

    async def link_otp_to_identity(self, identity_id: UUID, destination: str, channel: str) -> Credential:
        """
        Привязывает телефон/email как способ входа для существующей identity.
        """
        pass

    async def revoke_credential(self, credential_id: UUID) -> None:
        """
        Архивирует/отзывает credential.
        """
        pass

    # =============================================================
    # Sessions / JWT
    # =============================================================

    async def create_session(
        self,
        identity_id: UUID,
        client_app_id: UUID,
        **session_data,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Создаёт новую сессию:
        - генерирует access_token и refresh_token
        - хэширует refresh_token
        - сохраняет session
        - возвращает (session, (access, refresh))
        """
        # Получаем client_app для получения TTL
        client_app = await self.dao.client_apps.get_by_id(client_app_id)

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
            **session_data,)

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
        pass

    async def revoke_session(self, session_id: UUID) -> None:
        """
        Помечает сессию как revoked.
        """
        pass

    async def revoke_all_sessions(self, identity_id: UUID) -> None:
        """
        Отзывает все сессии пользователя.
        """
        pass

    async def list_sessions(self, identity_id: UUID) -> list[Session]:
        """
        Возвращает все активные/незавершённые сессии identity.
        """
        pass

    # =============================================================
    # Identity
    # =============================================================

    async def create_identity(self, *, tenant_id: Optional[str] = None) -> AuthIdentity:
        """
        Создаёт новую пустую identity без credential.
        """
        pass

    async def get_identity(self, identity_id: UUID) -> AuthIdentity:
        """Получает identity по ID."""
        return await self.dao.identities.get_by_id(identity_id)

    async def delete_identity(self, identity_id: UUID) -> None:
        """
        Мягкое удаление identity (status = deleted).
        """
        pass

    # =============================================================
    # External links
    # =============================================================

    async def link_external_user(self, identity_id: UUID, external_system: str, external_user_id: str) -> None:
        """
        Добавляет маппинг identity -> внешний пользователь (например фингуляр user_id).
        Нужен для дедупликации на стороне внешнего сервиса.
        """
        pass

    # =============================================================
    # Tokens
    # =============================================================

    async def build_jwt_payload(
        self,
        identity_id: UUID,
        client_app_id: UUID,  # noqa: ARG002
    ) -> dict:
        """
        1. Основные claims: sub, iat, exp, tenant
        2. Дёргает внешний сервис за бизнес-контекстом
        3. Возвращает итоговый payload
        """
        # Получаем identity для tenant_id
        identity = await self.get_identity(identity_id)

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

    # =============================================================
    # Maintenance / utils
    # =============================================================

    async def cleanup_expired_sessions(self) -> int:
        """
        Удаляет / архивирует истёкшие сессии.
        Возвращает число обработанных.
        """
        pass

    async def cleanup_expired_otp(self) -> int:
        """
        Чистит старые OTP-вызовы.
        """
        pass

    async def _stop(self):
        """Graceful shutdown."""
        pass
