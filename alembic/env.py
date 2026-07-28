import sqlalchemy as sa
from adc_aiopg.alembic_env import run_alembic

from services.repositories import DAO
from settings import cfg

# Схему нужно создать до того, как alembic создаст в ней auth.alembic_version
# (version_table_schema="auth"), иначе первый запуск на чистой БД падает.
engine = sa.create_engine(cfg.pg.connection.dsn)
with engine.begin() as connection:
    connection.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {DAO.meta.schema}"))
engine.dispose()

run_alembic(
    sqlalchemy_url=cfg.pg.connection.dsn,
    target_metadata=DAO.meta,
    configure_kwargs={"template_args": {"schema_name": DAO.meta.schema}, "version_table_schema": "auth"},
)
