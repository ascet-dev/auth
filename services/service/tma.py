"""Telegram Mini App."""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl

from models.enums import AuthMethod, CredentialType, IdentityStatus
from models.session import Session  # noqa: TC001
from settings import cfg

from .base import ServiceBase

if TYPE_CHECKING:
    from uuid import UUID


class TmaMixin(ServiceBase):
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
        connector: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, tuple[str, str]]:
        """
        Аутентификация через Telegram Mini App initData.

        1. Резолвит TMA-коннектор приложения (несколько ботов → явный `connector`)
        2. Верифицирует HMAC-подпись initData токеном бота коннектора
        3. Ищет credential по (type=TMA, external_subject_id=telegram_id) —
           telegram_id глобален, один юзер = одна identity через любых ботов
        4. Если нет — создаёт identity + TMA credential (connector_key в provider)
        5. Создаёт сессию
        """
        async with self.log_login_attempt(
            method="tma",
            identifier=connector,
            ip_address=ip_address,
            user_agent=user_agent,
        ) as logger:
            await self.ensure_public_client_app(client_app_id)
            connector_key, tma_settings = await self.resolve_auth_connector(
                AuthMethod.TMA,
                client_app_id,
                key=connector,
            )

            bot_token = tma_settings.get("bot_token")
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

                # Обновляем meta и last_used (+ последний использованный коннектор)
                await self.dao.credentials.update_by_id(
                    credential.id,
                    last_used=now,
                    provider=connector_key,
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

                # Создаём TMA credential (provider = коннектор, для аудита/будущей изоляции)
                credential = await self.dao.credentials.create(
                    identity_id=identity_id,
                    type=CredentialType.TMA,
                    identifier=tma_data.get("username"),
                    provider=connector_key,
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
