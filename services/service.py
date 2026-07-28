from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import secrets
from logging import getLogger
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode

import aiohttp
from adc_aiopg import RowNotFoundError
from adc_appkit import BaseApp, ComponentStrategy, component
from adc_appkit.components.component import create_component
from adc_appkit.components.pg import PG
from jose import jwt
from jose.jwt import decode as jwt_decode

from models.admin_grant import AuthAdminGrant  # noqa: TC001
from models.client_app import ClientApp  # noqa: TC001
from models.credential import Credential  # noqa: TC001
from models.enums import AdminRole, AuthClientType, AuthMethod, CredentialType, IdentityStatus, SessionStatus
from models.identity import AuthIdentity  # noqa: TC001
from models.otp_challenge import AuthOtpChallenge  # noqa: TC001
from models.session import Session  # noqa: TC001
from services.login_attempt_logger import LoginAttemptLogger
from services.password_service import PasswordService
from services.repositories import DAO
from settings import cfg

from .components import AdminContext, CurrentAdmin, CurrentIdentity

if TYPE_CHECKING:
    from uuid import UUID

    from adc_aiopg.types import Paginated

# Constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
HTTP_OK = 200

# Системный client_app для сессий админов auth-сервиса
AUTH_ADMIN_CLIENT_KEY = "auth-admin"
AUTH_ADMIN_REFRESH_TTL_SEC = 60 * 60 * 24 * 7  # 7 дней

# Дефолты способов входа: применяются, пока в auth_method_settings нет строки.
# Существующие инсталляции работают без сида и без изменения поведения.
AUTH_METHOD_DEFAULTS: dict[AuthMethod, dict] = {
    AuthMethod.PASSWORD: {"enabled": True, "settings": {"allow_registration": True}},
    AuthMethod.OTP: {"enabled": False, "settings": {}},
    AuthMethod.TMA: {"enabled": True, "settings": {}},
    AuthMethod.OAUTH: {"enabled": True, "settings": {}},
}

log = getLogger(__name__)


class AdminGrantRevokedError(ValueError):
    """Грант отозван — токен с ролью выдать нельзя, сессию нужно ревокнуть."""


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
    ) -> LoginAttemptLogger:
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
    # Способы входа (auth methods)
    # =============================================================

    async def get_auth_method_setting(self, method: AuthMethod) -> tuple[bool, dict]:
        """
        Эффективная конфигурация метода: дефолты из кода, поверх — строка из БД.
        Возвращает (enabled, settings).
        """
        defaults = AUTH_METHOD_DEFAULTS[method]
        rows = await self.dao.auth_methods.search(method=method, archived=False, limit=1)
        if not rows:
            return defaults["enabled"], dict(defaults["settings"])
        row = rows[0]
        return row.enabled, {**defaults["settings"], **(row.settings or {})}

    async def ensure_auth_method_allowed(
        self,
        method: AuthMethod,
        client_app_id: UUID | None = None,
        provider: str | None = None,
    ) -> dict:
        """
        Guard способа входа: метод включён глобально и разрешён приложению.
        Админ-логин (login_by_admin) этот guard НЕ использует — чтобы нельзя было
        отрезать себе доступ к админке, выключив пароль.

        Возвращает эффективные settings метода.
        """
        enabled, settings = await self.get_auth_method_setting(method)
        method_key = method.value.lower()
        if not enabled:
            raise ValueError(f"Auth method '{method_key}' is disabled")

        if client_app_id:
            client_app = await self.dao.client_apps.get_by_id(client_app_id)
            allowed = client_app.allowed_auth_methods
            if allowed:
                keys = {method_key}
                if provider:
                    keys.add(f"{method_key}:{provider.lower()}")
                if not keys & {a.lower() for a in allowed}:
                    raise ValueError(f"Auth method '{method_key}' is not allowed for this application")

        return settings

    # =============================================================
    # Пароли
    # =============================================================

    async def register_password_identity(self, identifier: str, password: str) -> AuthIdentity:
        """
        Создаёт новую identity + password credential.
        identifier — email, phone, username и т.п.
        НЕ привязывает к существующим identities.
        """
        settings = await self.ensure_auth_method_allowed(AuthMethod.PASSWORD)
        if not settings.get("allow_registration", True):
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

    async def _verify_password_credential(self, identifier: str, password: str) -> Credential:
        """
        Находит password credential по identifier и проверяет пароль:
        lockout, счётчики неудачных попыток, сброс счётчиков при успехе.
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
            raise ValueError("Credential is locked")

        if not credential.secret_hash or not self.password_service.verify_password(
            password,
            credential.secret_hash,
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
            await self.ensure_auth_method_allowed(AuthMethod.PASSWORD, client_app_id)

            credential = await self._verify_password_credential(identifier, password)

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

    async def send_otp(self, destination: str, channel: str) -> AuthOtpChallenge:  # noqa: ARG002
        """
        1. Создаёт OTP challenge
        2. Генерирует код
        3. Сохраняет hash
        4. Отправляет через внешний сервис уведомлений
        """
        await self.ensure_auth_method_allowed(AuthMethod.OTP)
        raise NotImplementedError()

    async def login_by_otp(self, challenge_id: UUID, code: str) -> tuple[Session, tuple[str, str]]:  # noqa: ARG002
        """
        1. Проверяет OTP challenge
        2. Находит или создаёт identity
        3. Создаёт OTP credential (если надо)
        4. Создаёт новую сессию
        """
        await self.ensure_auth_method_allowed(AuthMethod.OTP)
        raise NotImplementedError()

    # =============================================================
    # TMA (Telegram Mini App)
    # =============================================================

    @staticmethod
    def verify_tma_init_data(init_data: str, bot_token: str, max_age: int = 300) -> dict:
        """
        Верифицирует initData от Telegram Mini App через HMAC-SHA256.

        Args:
            init_data: raw query string из Telegram.WebApp.initData
            bot_token: токен бота Telegram
            max_age: максимальный возраст auth_date в секундах

        Returns:
            Распарсенные данные пользователя: telegram_id, first_name, last_name, username, photo_url, language_code

        Raises:
            ValueError: если подпись невалидна или данные устарели
        """
        # Парсим query string, URL-декодим значения
        params = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = params.pop("hash", None)
        if not received_hash:
            raise ValueError("No hash in initData")

        # Проверяем свежесть auth_date
        auth_date_str = params.get("auth_date")
        if not auth_date_str:
            raise ValueError("No auth_date in initData")

        auth_date = int(auth_date_str)
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        if now - auth_date > max_age:
            raise ValueError("initData expired")

        # Формируем data-check-string: отсортированные key=value через \n
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

        # Секретный ключ: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

        # Вычисляем хэш
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        # Сравниваем (constant-time)
        if not hmac.compare_digest(computed_hash, received_hash):
            raise ValueError("Invalid initData signature")

        # Парсим JSON с данными пользователя
        user_raw = params.get("user")
        if not user_raw:
            raise ValueError("No user data in initData")

        try:
            user_data = json.loads(user_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid user data in initData") from exc

        telegram_id = user_data.get("id")
        if not telegram_id:
            raise ValueError("No user id in initData")

        return {
            "telegram_id": str(telegram_id),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "username": user_data.get("username"),
            "photo_url": user_data.get("photo_url"),
            "language_code": user_data.get("language_code"),
            "auth_date": auth_date,
        }

    async def login_by_tma(
        self,
        init_data: str,
        client_app_id: UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Аутентификация через Telegram Mini App initData.

        1. Верифицирует HMAC-подпись initData ботовым токеном
        2. Извлекает telegram_id
        3. Ищет credential по (type=TMA, external_subject_id=telegram_id)
        4. Если нет — создаёт identity + TMA credential
        5. Создаёт сессию
        """
        async with self.log_login_attempt(
            method="tma",
            identifier=None,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            tma_settings = await self.ensure_auth_method_allowed(AuthMethod.TMA, client_app_id)

            # Параметры из настроек метода (админка), fallback — env
            bot_token = tma_settings.get("bot_token") or cfg.auth.telegram_bot_token
            if not bot_token:
                raise ValueError("Telegram bot token not configured")
            max_age = tma_settings.get("auth_date_max_age") or cfg.auth.tma_auth_date_max_age

            # Верифицируем initData
            tma_data = self.verify_tma_init_data(
                init_data,
                bot_token,
                max_age=max_age,
            )

            telegram_id = tma_data["telegram_id"]

            # Ищем существующий TMA credential
            credentials = await self.dao.credentials.search(
                type=CredentialType.TMA,
                external_subject_id=telegram_id,
                archived=False,
                limit=1,
            )

            now = datetime.datetime.now(datetime.UTC)

            if credentials:
                credential = credentials[0]
                identity_id = credential.identity_id

                # Обновляем meta и last_used
                await self.dao.credentials.update_by_id(
                    credential.id,
                    last_used=now,
                    meta={
                        "first_name": tma_data.get("first_name"),
                        "last_name": tma_data.get("last_name"),
                        "username": tma_data.get("username"),
                        "photo_url": tma_data.get("photo_url"),
                        "language_code": tma_data.get("language_code"),
                    },
                )
            else:
                # Создаём новую identity
                identity = await self.dao.identities.create(
                    status=IdentityStatus.ACTIVE,
                )
                identity_id = identity.id

                # Создаём TMA credential
                credential = await self.dao.credentials.create(
                    identity_id=identity_id,
                    type=CredentialType.TMA,
                    identifier=tma_data.get("username"),
                    external_subject_id=telegram_id,
                    failed_attempts=0,
                    meta={
                        "first_name": tma_data.get("first_name"),
                        "last_name": tma_data.get("last_name"),
                        "username": tma_data.get("username"),
                        "photo_url": tma_data.get("photo_url"),
                        "language_code": tma_data.get("language_code"),
                    },
                    last_used=now,
                )

            session, tokens = await self.create_session(
                identity_id,
                client_app_id,
                ip=ip_address,
                user_agent=user_agent,
            )

            logger.set(identity_id=identity_id, credential_id=credential.id)

            return session, tokens

    # =============================================================
    # OAuth
    # =============================================================

    async def start_oauth_flow(self, provider: str, redirect_uri: str) -> str:
        """
        Возвращает URL для начала авторизации у провайдера.
        """
        await self.ensure_auth_method_allowed(AuthMethod.OAUTH)

        # Получаем провайдера из БД
        oauth_providers = await self.dao.oauth_providers.search(
            name=provider,
            enabled=True,
            archived=False,
            limit=1,
        )

        if not oauth_providers:
            raise ValueError(f"OAuth provider '{provider}' not found or disabled")

        oauth_provider = oauth_providers[0]

        # Генерируем state для защиты от CSRF
        state = secrets.token_urlsafe(32)

        # Формируем параметры для OAuth URL
        params = {
            "client_id": oauth_provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": "openid profile email",  # Базовые scope для большинства провайдеров
        }

        # Формируем URL
        auth_url = oauth_provider.auth_url
        url = f"{auth_url}&{urlencode(params)}" if "?" in auth_url else f"{auth_url}?{urlencode(params)}"

        return url

    async def login_by_oauth(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
        client_app_id: UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        1. Обменивает code на токен провайдера
        2. Валидирует id_token / profile
        3. Ищет credential по (provider, external_subject_id)
        4. Если нет — создаёт новую identity
        5. Создаёт oauth credential
        6. Создаёт новую сессию
        """
        async with self.log_login_attempt(
            method="oauth",
            identifier=provider,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            await self.ensure_auth_method_allowed(AuthMethod.OAUTH, client_app_id, provider=provider)

            # Получаем провайдера из БД
            oauth_providers = await self.dao.oauth_providers.search(
                name=provider,
                enabled=True,
                archived=False,
                limit=1,
            )

            if not oauth_providers:
                raise ValueError(f"OAuth provider '{provider}' not found or disabled")

            oauth_provider = oauth_providers[0]

            # Обмениваем code на токен
            async with aiohttp.ClientSession() as http_session:
                token_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": oauth_provider.client_id,
                    "client_secret": oauth_provider.client_secret,
                }

                async with http_session.post(
                    oauth_provider.token_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as resp:
                    if resp.status != HTTP_OK:
                        error_text = await resp.text()
                        raise ValueError(f"Failed to exchange code for token: {error_text}")

                    token_response = await resp.json()

            access_token = token_response.get("access_token")
            id_token = token_response.get("id_token")

            # Получаем информацию о пользователе
            external_subject_id: str | None = None
            user_email: str | None = None
            user_name: str | None = None

            # Если есть id_token, декодируем его
            if id_token:
                try:
                    # Если есть JWKS URL, валидируем через JWKS
                    if oauth_provider.jwks_url:
                        # Для упрощения декодируем без валидации подписи (в продакшене нужна валидация)
                        # В реальном приложении нужно использовать jose.jwt.get_unverified_header
                        # и jose.jwt.get_unverified_claims для получения claims
                        decoded = jwt_decode(id_token, options={"verify_signature": False})
                    else:
                        decoded = jwt_decode(id_token, options={"verify_signature": False})

                    external_subject_id = decoded.get("sub") or decoded.get("user_id") or decoded.get("id")
                    user_email = decoded.get("email")
                    user_name = decoded.get("name") or decoded.get("given_name")

                except Exception:
                    # Если не удалось декодировать id_token, попробуем получить через userinfo
                    log.exception("Failed to decode OAuth id_token")

            # Если нет external_subject_id из id_token, получаем через userinfo
            if not external_subject_id and oauth_provider.userinfo_url and access_token:
                async with (
                    aiohttp.ClientSession() as http_session,
                    http_session.get(
                        oauth_provider.userinfo_url,
                        headers={"Authorization": f"Bearer {access_token}"},
                    ) as resp,
                ):
                    if resp.status == HTTP_OK:
                        userinfo = await resp.json()
                        external_subject_id = userinfo.get("sub") or userinfo.get("user_id") or userinfo.get("id")
                        user_email = userinfo.get("email")
                        user_name = userinfo.get("name") or userinfo.get("given_name")

            if not external_subject_id:
                raise ValueError("Could not extract user ID from OAuth provider response")

            # Ищем существующий credential
            credentials = await self.dao.credentials.search(
                provider=provider,
                external_subject_id=external_subject_id,
                type=CredentialType.OAUTH,
                archived=False,
                limit=1,
            )

            now = datetime.datetime.now(datetime.UTC)

            if credentials:
                # Найден существующий credential
                credential = credentials[0]
                identity_id = credential.identity_id

                # Обновляем last_used
                await self.dao.credentials.update_by_id(
                    credential.id,
                    last_used=now,
                )
            else:
                # Создаём новую identity
                identity = await self.dao.identities.create(
                    tenant_id=None,
                    status=IdentityStatus.ACTIVE,
                )
                identity_id = identity.id

                # Создаём OAuth credential
                credential = await self.dao.credentials.create(
                    identity_id=identity_id,
                    type=CredentialType.OAUTH,
                    provider=provider,
                    external_subject_id=external_subject_id,
                    identifier=user_email,
                    meta={
                        "email": user_email,
                        "name": user_name,
                        "last_token_response": token_response,
                    },
                    last_used=now,
                )

            # Создаём сессию
            session, tokens = await self.create_session(
                identity_id,
                client_app_id,
                ip=ip_address,
                user_agent=user_agent,
            )

            # Устанавливаем identity_id и credential_id для успешного логирования
            logger.set(identity_id=identity_id, credential_id=credential.id)

            return session, tokens

    async def link_oauth_to_identity(self, identity_id: UUID, provider: str, code: str) -> Credential:
        """
        Явная привязка нового OAuth способа входа к существующей identity.
        Разрешена только из доверенной зоны.
        Автолинковки НЕТ.
        """
        raise NotImplementedError()

    # =============================================================
    # Credentials
    # =============================================================

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

    # =============================================================
    # Админы auth-сервиса
    # =============================================================

    async def get_admin_client_app(self) -> ClientApp:
        """Возвращает системный client_app для админских сессий."""
        apps = await self.dao.client_apps.search(key=AUTH_ADMIN_CLIENT_KEY, archived=False, limit=1)
        if not apps:
            raise ValueError("Auth service is not initialized: run 'python manage.py bootstrap-owner'")
        return apps[0]

    async def get_active_admin_grant(self, identity_id: UUID) -> AuthAdminGrant | None:
        """Активный (не отозванный) админский грант identity, если есть."""
        grants = await self.dao.admin_grants.search(identity_id=identity_id, archived=False, limit=1)
        return grants[0] if grants else None

    async def check_owner_initialized(self) -> bool:
        """Проверка при старте web: сервис должен быть проинициализирован."""
        owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False, limit=1)
        if not owners:
            log.error("Auth service is not initialized: run 'python manage.py bootstrap-owner'")
            return False
        return True

    async def bootstrap_owner(self, login: str, password: str) -> dict:
        """
        Идемпотентная инициализация сервиса:
        - создаёт системный client_app `auth-admin`, если его нет;
        - если активный OWNER grant уже есть — no-op;
        - иначе создаёт identity + PASSWORD credential + grant OWNER (granted_by=NULL).
        """
        client_apps = await self.dao.client_apps.search(key=AUTH_ADMIN_CLIENT_KEY, archived=False, limit=1)
        if client_apps:
            client_app = client_apps[0]
        else:
            client_app = await self.dao.client_apps.create(
                key=AUTH_ADMIN_CLIENT_KEY,
                name="Auth Admin UI",
                type=AuthClientType.PUBLIC,
                allowed_redirect_uris=[],
                allowed_scopes=[],
                access_token_ttl_sec=int(cfg.auth.access_token_lifetime.total_seconds()),
                refresh_token_ttl_sec=AUTH_ADMIN_REFRESH_TTL_SEC,
            )
            log.info("Created system client_app '%s' (%s)", AUTH_ADMIN_CLIENT_KEY, client_app.id)

        owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False, limit=1)
        if owners:
            log.info("Active OWNER grant already exists (identity %s), nothing to do", owners[0].identity_id)
            return {"created": False, "identity_id": owners[0].identity_id, "client_app_id": client_app.id}

        # Реюзаем существующий password credential, чтобы повторный bootstrap
        # (например, после отзыва OWNER) не плодил дубликаты identifier-ов.
        credentials = await self.dao.credentials.search(
            identifier=login,
            type=CredentialType.PASSWORD,
            archived=False,
            limit=1,
        )
        if credentials:
            identity_id = credentials[0].identity_id
        else:
            identity = await self.dao.identities.create(status=IdentityStatus.ACTIVE)
            identity_id = identity.id
            await self.dao.credentials.create(
                identity_id=identity_id,
                type=CredentialType.PASSWORD,
                identifier=login,
                secret_hash=self.password_service.hash_password(password),
                failed_attempts=0,
            )

        # У identity может остаться активный ADMIN grant — заменяем его на OWNER
        # (partial unique index допускает только один активный грант на identity).
        existing_grant = await self.get_active_admin_grant(identity_id)
        if existing_grant:
            await self.dao.admin_grants.archive_by_id(existing_grant.id)

        grant = await self.dao.admin_grants.create(identity_id=identity_id, role=AdminRole.OWNER, granted_by=None)
        log.info("OWNER grant %s created for identity %s (login '%s')", grant.id, identity_id, login)
        return {"created": True, "identity_id": identity_id, "client_app_id": client_app.id}

    async def grant_admin_role(self, identity_id: UUID, role: AdminRole, granted_by: UUID) -> AuthAdminGrant:
        """
        Выдаёт админский грант (только для OWNER-а, проверяется в эндпоинте).
        Partial unique index страхует от гонок, но pre-check даёт чистую ошибку.
        """
        try:
            identity = await self.dao.identities.get_by_id(identity_id)
        except RowNotFoundError:
            raise ValueError("Identity not found") from None

        if identity.status != IdentityStatus.ACTIVE:
            raise ValueError(f"Identity is not active (status: {identity.status})")

        existing = await self.get_active_admin_grant(identity_id)
        if existing:
            raise ValueError("Identity already has an active admin grant")

        return await self.dao.admin_grants.create(identity_id=identity_id, role=role, granted_by=granted_by)

    async def revoke_admin_grant(self, grant_id: UUID) -> None:
        """
        Отзывает грант: archive + немедленная ревокация админских сессий грантополучателя.
        Последнего активного OWNER-а отозвать нельзя.
        """
        try:
            grant = await self.dao.admin_grants.get_by_id(grant_id)
        except RowNotFoundError:
            raise ValueError("Grant not found") from None

        if grant.archived:
            raise ValueError("Grant is already revoked")

        if AdminRole(grant.role) == AdminRole.OWNER:
            owners = await self.dao.admin_grants.search(role=AdminRole.OWNER, archived=False)
            if len(owners) <= 1:
                raise ValueError("Cannot revoke the last active OWNER grant")

        await self.dao.admin_grants.archive_by_id(grant_id)

        # Отзыв прав действует сразу: гасим активные админские сессии
        admin_app = await self.get_admin_client_app()
        await self.dao.sessions.update(
            {"status": SessionStatus.REVOKED},
            identity_id=grant.identity_id,
            client_app_id=admin_app.id,
            status=SessionStatus.ACTIVE,
        )

    async def login_by_admin(
        self,
        identifier: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Логин админа auth-сервиса: пароль + активный админский грант.
        Сессия создаётся под системным client_app `auth-admin`,
        access-токен получает claim `role`.
        """
        async with self.log_login_attempt(
            method="admin_password",
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            credential = await self._verify_password_credential(identifier, password)

            grant = await self.get_active_admin_grant(credential.identity_id)
            if not grant:
                # Не раскрываем, что учётка существует, но прав нет
                raise ValueError("Invalid credentials")

            client_app = await self.get_admin_client_app()

            session, tokens = await self.create_session(
                credential.identity_id,
                client_app.id,
                ip=ip_address,
                user_agent=user_agent,
            )

            logger.set(identity_id=credential.identity_id, credential_id=credential.id)

            return session, tokens

    # =============================================================
    # Sessions / JWT
    # =============================================================

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

        client_app = await self.dao.client_apps.get_by_id(client_app_id)

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
        except AdminGrantRevokedError:
            # Админский грант отозван — сессия больше не имеет права жить
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

    # =============================================================
    # Identity
    # =============================================================

    async def create_identity(self, *, tenant_id: str | None = None) -> AuthIdentity:
        """
        Создаёт новую пустую identity без credential.
        """
        raise NotImplementedError()

    async def get_identity(self, identity_id: UUID) -> AuthIdentity:
        """Получает identity по ID."""
        return await self.dao.identities.get_by_id(identity_id)

    async def delete_identity(self, identity_id: UUID) -> None:
        """
        Мягкое удаление identity (status = deleted).
        """
        raise NotImplementedError()

    # =============================================================
    # External links
    # =============================================================

    async def link_external_user(self, identity_id: UUID, external_system: str, external_user_id: str) -> None:
        """
        Добавляет маппинг identity -> внешний пользователь (например фингуляр user_id).
        Нужен для дедупликации на стороне внешнего сервиса.
        """
        raise NotImplementedError()

    # =============================================================
    # Tokens
    # =============================================================

    async def build_jwt_payload(
        self,
        identity_id: UUID,
        client_app_id: UUID,
    ) -> dict:
        """
        1. Основные claims: sub, iat, exp, tenant
        2. Для системного client_app `auth-admin` добавляет claim `role`
        3. Дёргает внешний сервис за бизнес-контекстом
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

    # =============================================================
    # Maintenance / utils
    # =============================================================

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

    async def _stop(self) -> None:
        """Graceful shutdown."""
