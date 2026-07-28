import typing as t

from adc_aiopg.enum import sqla_enum
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AuthMethod


class AuthConnector(BaseModel):
    """
    Экземпляр способа входа (по образцу Auth0 connections / Keycloak IdP).

    Одного типа может быть сколько угодно: два TMA-бота, два Google-приложения,
    разные парольные политики. Привязка к приложениям — auth_client_app_connectors
    (пустая привязка приложения = все включённые коннекторы).

    settings по типам:
      PASSWORD: max_failed_attempts, lockout_minutes, allow_registration
      TMA:      bot_token (write-only), auth_date_max_age
      OAUTH:    client_id, client_secret (write-only), auth_url, token_url,
                jwks_url, userinfo_url
      OTP:      конфиг канала (когда будет реализован)

    Если коннекторов типа нет вообще — работают встроенные дефолты
    (PASSWORD: политика из констант; TMA: bot token из env).
    """

    # Слаг: "tma-shop-bot", "google-web", "password-default".
    # Для OAUTH это значение параметра `provider` в /auth/oauth/*.
    key: str

    type: AuthMethod = Field(sa_column=sqla_enum(AuthMethod).sa_column)

    name: str

    enabled: bool = Field(default=True)

    settings: dict[str, t.Any] | None = Field(default=None, sa_column=Column(JSONB))
