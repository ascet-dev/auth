from uuid import UUID

from adc_aiopg.types import Base
from adc_webkit.web.auth import JWT

from models.enums import AdminRole
from settings import cfg

__all__ = ("admin_jwt", "jwt")


class Client(Base):
    sub: UUID
    exp: int
    type: str


class AdminClient(Client):
    # Обязательное поле: токен без role (обычный пользовательский) не пройдёт
    # валидацию payload_model и получит 401.
    role: AdminRole


jwt = JWT(
    public_key=cfg.auth.public_key,
    payload_model=Client,
    algorithms=cfg.auth.algorithms,
)

admin_jwt = JWT(
    public_key=cfg.auth.public_key,
    payload_model=AdminClient,
    algorithms=cfg.auth.algorithms,
)
