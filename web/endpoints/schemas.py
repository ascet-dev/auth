from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel


class RegisterPasswordRequest(PydanticBaseModel):
    login: str
    password: str


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


class RevokedSessionsResponse(PydanticBaseModel):
    revoked_sessions: int
