from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel


class RegisterPasswordRequest(PydanticBaseModel):
    login: str
    password: str
    # Опционально: политика регистрации берётся из password-коннектора приложения
    client_app_id: UUID | None = None


class LoginByPasswordRequest(PydanticBaseModel):
    login: str
    password: str
    client_app_id: UUID


class SessionWithTokens(PydanticBaseModel):
    session: dict
    access_token: str
    refresh_token: str


class RefreshSessionRequest(PydanticBaseModel):
    refresh_token: str
    client_app_id: UUID


class RevokeSessionRequest(PydanticBaseModel):
    session_id: UUID


class OkResponse(PydanticBaseModel):
    ok: bool = True


class StartOAuthRequest(PydanticBaseModel):
    provider: str
    redirect_uri: str


class StartOAuthResponse(PydanticBaseModel):
    redirect_url: str


class LoginByOAuthRequest(PydanticBaseModel):
    provider: str
    code: str
    redirect_uri: str
    client_app_id: UUID


class LoginByTMARequest(PydanticBaseModel):
    init_data: str
    client_app_id: UUID
    # key TMA-коннектора; обязателен, если приложению доступно несколько ботов
    connector: str | None = None


class RevokedSessionsResponse(PydanticBaseModel):
    revoked_sessions: int


class AdminLoginRequest(PydanticBaseModel):
    login: str
    password: str


class AdminRefreshRequest(PydanticBaseModel):
    # client_app_id не нужен: админские сессии живут под системным client_app
    refresh_token: str


class AdminMeResponse(PydanticBaseModel):
    identity_id: UUID
    role: str
