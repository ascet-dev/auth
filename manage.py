import asyncio
import platform
from logging import getLogger

from adc_appkit.components.pg import PG
import click
import sentry_sdk

from settings import cfg
from web.app import web

cfg.logs.config.setup_logging()

logger = getLogger(__name__)


@click.group()
def cli():
    """Init event loop, logging config etc."""
    if cfg.logs.sentry.enabled:
        sentry_sdk.init(
            dsn=cfg.logs.sentry.dsn,
            integrations=cfg.logs.sentry.integrations,
            environment=cfg.env,
        )

    if platform.system() != "Windows":
        import uvloop  # noqa: WPS433 - will fail on Windows

        uvloop.install()


@cli.command(short_help="start web")
def start_web():
    """Start REST API application."""
    try:
        asyncio.run(web.start(host=cfg.app.host, port=cfg.app.port, logs_config=cfg.logs.config.get_logging_config()))
    except KeyboardInterrupt:
        logger.critical("Server stopped by user")


@cli.command(short_help="apply sql")
@click.argument("file_path", type=click.Path(exists=True))
def apply_sql(file_path: str) -> None:
    """Apply SQL script file"""
    from adc_appkit.components.pg import PG

    async def do() -> None:
        async with PG(config=cfg.pg.connection.dict()) as pool:
            with open(file_path) as file:
                sql_script = file.read()
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
        async with PG(config=cfg.pg.connection.model_dump()) as pool:
            with open("data/init_data.sql") as file:
                sql_script = file.read()
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
