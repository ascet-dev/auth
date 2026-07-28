import typing as t

from adc_aiopg.enum import sqla_enum
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from models.base import BaseModel
from models.enums import AuthMethod


class AuthMethodSetting(BaseModel):
    """
    Глобальная конфигурация способа входа.

    Отсутствие строки = дефолты из кода (AUTH_METHOD_DEFAULTS в services/service.py),
    поэтому существующие инсталляции работают без сида.
    Разрешение метода конкретному приложению — ClientApp.allowed_auth_methods.
    """

    method: AuthMethod = Field(sa_column=sqla_enum(AuthMethod).sa_column)

    enabled: bool = Field(default=True)

    # Параметры метода. PASSWORD: {"allow_registration": bool}.
    # TMA: {"bot_token": str (write-only), "auth_date_max_age": int} — null = fallback на env.
    settings: dict[str, t.Any] | None = Field(default=None, sa_column=Column(JSONB))
