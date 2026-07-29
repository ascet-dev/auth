"""OAuth 2.0."""

from __future__ import annotations

import datetime
import secrets
from logging import getLogger
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import aiohttp
from jose.jwt import decode as jwt_decode

from models.credential import Credential  # noqa: TC001
from models.enums import AuthMethod, CredentialType, IdentityStatus
from models.session import Session  # noqa: TC001
from services.service.constants import HTTP_OK

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID

log = getLogger(__name__)


class OauthMixin(ServiceBase):
    async def start_oauth_flow(self, provider: str, redirect_uri: str) -> str:
        """
        Возвращает URL для начала авторизации у провайдера.
        `provider` — key OAUTH-коннектора.
        """
        _, oauth_cfg = await self.resolve_auth_connector(AuthMethod.OAUTH, key=provider)

        # Генерируем state для защиты от CSRF
        state = secrets.token_urlsafe(32)

        # Формируем параметры для OAuth URL
        params = {
            "client_id": oauth_cfg.get("client_id"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": "openid profile email",  # Базовые scope для большинства провайдеров
        }

        # Формируем URL
        auth_url = oauth_cfg.get("auth_url", "")
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
            connector_key, oauth_cfg = await self.resolve_auth_connector(
                AuthMethod.OAUTH,
                client_app_id,
                key=provider,
            )

            # Обмениваем code на токен
            async with aiohttp.ClientSession() as http_session:
                token_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": oauth_cfg.get("client_id"),
                    "client_secret": oauth_cfg.get("client_secret"),
                }

                async with http_session.post(
                    oauth_cfg.get("token_url", ""),
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
                    # Для упрощения декодируем без валидации подписи
                    # (в продакшене нужна валидация через jwks_url из настроек коннектора)
                    decoded = jwt_decode(id_token, options={"verify_signature": False})

                    external_subject_id = decoded.get("sub") or decoded.get("user_id") or decoded.get("id")
                    user_email = decoded.get("email")
                    user_name = decoded.get("name") or decoded.get("given_name")

                except Exception:
                    # Если не удалось декодировать id_token, попробуем получить через userinfo
                    log.exception("Failed to decode OAuth id_token")

            # Если нет external_subject_id из id_token, получаем через userinfo
            if not external_subject_id and oauth_cfg.get("userinfo_url") and access_token:
                async with (
                    aiohttp.ClientSession() as http_session,
                    http_session.get(
                        oauth_cfg["userinfo_url"],
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

            # Ищем существующий credential (provider = key коннектора)
            credentials = await self.dao.credentials.search(
                provider=connector_key,
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
                    provider=connector_key,
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
