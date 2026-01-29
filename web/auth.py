from uuid import UUID

from adc_aiopg.types import Base
from adc_webkit.web.auth import JWT

from settings import cfg

__all__ = ("jwt",)


class Client(Base):
    sub: UUID
    exp: int
    type: str


jwt = JWT(
    public_key=cfg.auth.public_key,
    payload_model=Client,
    algorithms=cfg.auth.algorithms,
)
