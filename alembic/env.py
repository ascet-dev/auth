from adc_aiopg.alembic_env import run_alembic

from services.repositories import DAO
from settings import cfg

run_alembic(
    sqlalchemy_url=cfg.pg.connection.dsn,
    target_metadata=DAO.meta,
    configure_kwargs={"template_args": {"schema_name": DAO.meta.schema}},
)
