from __future__ import annotations

import datetime
from typing import Optional, Tuple
from uuid import UUID

from adc_appkit import BaseApp, ComponentStrategy, component
from adc_appkit.components.component import create_component
from adc_appkit.components.pg import PG
from models.credential import Credential
from models.session import Session

from models.client_app import ClientApp
from models.identity import AuthIdentity
from models.oauth_provider import AuthOauthProvider
from models.otp_challenge import AuthOtpChallenge
from services.repositories import DAO


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

    dao: DAO = component(
        create_component(DAO),
        dependencies={"pool": "pg"},
        config_key="dao",
        strategy=ComponentStrategy.REQUEST,
    )

    # def __init__(self, *args, tokens_config: dict, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.tokens_config = tokens_config

    # =============================================================
    # Пароли
    # =============================================================

    async def register_password_identity(self, email: str, password: str) -> AuthIdentity:
        """
        Создаёт новую identity + password credential.
        НЕ привязывает к существующим identities.
        """
        pass

    async def login_by_password(self, identifier: str, password: str) -> Tuple[Session, Tuple[str, str]]:
        """
        Находит credential по type=password и identifier.
        Проверяет пароль.
        Создаёт новую сессию.
        """
        pass

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

    async def login_by_otp(self, challenge_id: UUID, code: str) -> Tuple[Session, Tuple[str, str]]:
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

    async def login_by_oauth(self, provider: str, code: str, redirect_uri: str) -> Tuple[Session, Tuple[str, str]]:
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

    async def create_session(self, identity_id: UUID, client_app_id: UUID) -> Tuple[Session, Tuple[str, str]]:
        """
        Создаёт новую сессию:
        - генерирует access_token и refresh_token
        - хэширует refresh_token
        - сохраняет session
        - возвращает (session, (access, refresh))
        """
        pass

    async def refresh_session(
        self,
        refresh_token: str,
        client_app_id: UUID,
    ) -> Tuple[Session, Tuple[str, str]]:
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
        pass

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

    async def build_jwt_payload(self, identity_id: UUID, client_app_id: str) -> dict:
        """
        1. Основные claims: sub, iat, exp, tenant
        2. Дёргает внешний сервис за бизнес-контекстом
        3. Возвращает итоговый payload
        """
        pass

    async def generate_access_token(self, payload: dict) -> str:
        """
        Создаёт короткоживущий access JWT.
        """
        pass

    async def generate_refresh_token(self) -> str:
        """
        Генерирует длинный opaque token для сессии.
        """
        pass

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
