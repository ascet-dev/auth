from pydantic import Field
from pydantic_settings import BaseSettings


class Cors(BaseSettings):
    allow_origins: list[str] = ["*"]
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]
    allow_credentials: bool = True


class App(BaseSettings):
    host: str = "localhost"  # noqa: S104
    port: int = 8002
    client_max_size: int = 1024 * 1024 * 50
    base_url: str = "/"
    cors: Cors = Field(default_factory=Cors)
