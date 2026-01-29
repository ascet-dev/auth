from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .app import App
from .auth import Auth
from .doc import Doc
from .env import ENV
from .logs import Logging
from .postgres import PG
from .s3 import S3


class CFG(BaseSettings):
    env: str = ENV
    app: App = Field(default_factory=App)
    doc: Doc = Field(default_factory=Doc)
    auth: Auth = Field(default_factory=Auth)
    logs: Logging = Field(default_factory=Logging)
    pg: PG = Field(default_factory=PG)
    s3: S3 = Field(default_factory=S3)

    class Config:
        env_prefix = ""
        model_config = SettingsConfigDict(validate_default=False)
        env_file = ".env" if ENV == "LOCAL" else None
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        extra = "ignore"
