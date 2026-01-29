import asyncio
import platform
from logging import getLogger
from pathlib import Path

import click
import sentry_sdk
from adc_appkit.components.pg import PG

from settings import cfg
from web.app import web

cfg.logs.config.setup_logging()

logger = getLogger(__name__)


@click.group()
def cli() -> None:
    """Init event loop, logging config etc."""
    if cfg.logs.sentry.enabled:
        sentry_sdk.init(
            dsn=cfg.logs.sentry.dsn,
            integrations=cfg.logs.sentry.integrations,
            environment=cfg.env,
        )

    if platform.system() != "Windows":
        import uvloop  # will fail on Windows

        uvloop.install()


@cli.command(short_help="start web")
def start_web() -> None:
    """Start REST API application."""
    try:
        asyncio.run(web.start(host=cfg.app.host, port=cfg.app.port, logs_config=cfg.logs.config.get_logging_config()))
    except KeyboardInterrupt:
        logger.critical("Server stopped by user")


@cli.command(short_help="apply sql")
@click.argument("file_path", type=click.Path(exists=True))
def apply_sql(file_path: str) -> None:
    """Apply SQL script file"""

    async def do() -> None:
        pg = PG()
        pg.set_config(cfg.pg.connection.model_dump())
        async with pg as pool:
            sql_script = Path(file_path).read_text(encoding="utf-8")
            res = await pool.execute(sql_script)
            logger.debug(res)

    try:
        asyncio.run(do())
    except KeyboardInterrupt:
        logger.critical("Command stopped by user")


@cli.command(short_help="seed data")
def seed_data() -> None:
    """Add test data (admin:admin user)"""

    async def do() -> None:
        pg = PG()
        pg.set_config(cfg.pg.connection.model_dump())
        async with pg as pool:
            sql_script = Path("data/init_data.sql").read_text(encoding="utf-8")
            res = await pool.execute(sql_script)
            logger.debug(res)

    try:
        asyncio.run(do())
    except KeyboardInterrupt:
        logger.critical("Command stopped by user")
    except Exception as e:
        logger.error(e)


if __name__ == "__main__":
    cli()
