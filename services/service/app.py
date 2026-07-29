"""Сборка приложения: компоненты + миксины бизнес-логики."""

from __future__ import annotations

from adc_appkit import BaseApp, ComponentStrategy, component
from adc_appkit.components.component import create_component
from adc_appkit.components.pg import PG

from services.components import AdminContext, CurrentAdmin, CurrentIdentity
from services.login_attempt_logger import LoginAttemptLogger
from services.password_service import PasswordService
from services.repositories import DAO

from .admin import AdminMixin
from .base import ServiceBase
from .connectors import ConnectorsMixin
from .credentials import CredentialsMixin
from .identity import IdentityMixin
from .maintenance import MaintenanceMixin
from .oauth import OauthMixin
from .otp import OtpMixin
from .passwords import PasswordsMixin
from .sessions import SessionsMixin
from .tma import TmaMixin
from .tokens import TokensMixin


class App(  # noqa: PLR0904
    ConnectorsMixin,
    PasswordsMixin,
    OtpMixin,
    TmaMixin,
    OauthMixin,
    CredentialsMixin,
    AdminMixin,
    SessionsMixin,
    IdentityMixin,
    TokensMixin,
    MaintenanceMixin,
    ServiceBase,
    BaseApp,
):
    """
    Универсальный сервис аутентификации, который:
    - управляет identities, credentials и sessions;
    - работает с OTP, паролями, OAuth провайдерами;
    - ничего не знает о бизнес-логике внешних систем;
    - получает дополнительные claims для JWT из внешнего сервиса;
    - НЕ делает автолинковки credential → identity.

    Логика разложена по миксинам (см. соседние модули), здесь — только
    подключение компонентов и общие для всех методов утилиты.
    """

    pg = component(PG, config_key="pg")
    dao: DAO = component(create_component(DAO), dependencies={"pool": "pg"}, config_key="dao")
    password_service: PasswordService = PasswordService()
    current_identity: CurrentIdentity = component(
        CurrentIdentity,
        config_key="current_identity",
        strategy=ComponentStrategy.REQUEST,
    )
    # Аннотация — тип значения в request scope (результат _start), не тип компонента
    current_admin: AdminContext = component(
        CurrentAdmin,
        config_key="current_admin",
        strategy=ComponentStrategy.REQUEST,
    )

    def log_login_attempt(
        self,
        method: str,
        identifier: str | None = None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginAttemptLogger:
        """
        Контекстный менеджер для логирования попыток входа.

        Логирует как успешные, так и неудачные попытки входа.

        Usage:
            async with app.log_login_attempt(method='password', identifier=identifier) as logger:
                session, tokens = await self.create_session(...)
                logger.set(identity_id=..., credential_id=...)
                return session, tokens
        """
        return LoginAttemptLogger(
            dao=self.dao,
            method=method,
            identifier=identifier,
            ip_address=ip_address or "",
            user_agent=user_agent or "",
        )

    async def _stop(self) -> None:
        """Graceful shutdown."""
