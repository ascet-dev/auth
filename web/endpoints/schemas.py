from models.base import BaseModel

class LoginByPasswordRequest(BaseModel):
    login: str
    password: str
