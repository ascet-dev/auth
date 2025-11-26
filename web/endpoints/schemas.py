from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel


class LoginByPasswordRequest(PydanticBaseModel):
    login: str
    password: str
    client_app_id: UUID


class SessionWithTokens(PydanticBaseModel):
    session: dict
    access_token: str
    refresh_token: str
