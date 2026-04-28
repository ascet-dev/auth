from pydantic_settings import BaseSettings


class Connection(BaseSettings):
    dsn: str = "postgresql://postgres:postgres@localhost:5432/auth"
    min_size: int = 1
    max_size: int = 2
    max_inactive_connection_lifetime: int = 300
    timeout: int = 60
    statement_cache_size: int = 1024


class PG(BaseSettings):
    connection: Connection = Connection()
    schema_name: str = "auth"
