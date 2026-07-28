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
    """Auth service CLI."""
    if platform.system() != "Windows":
        import uvloop

        uvloop.install()


@cli.command(short_help="start web")
def start_web() -> None:
    """Start REST API application."""
    # Дефолтные ключи лежат в публичном репозитории: с ними кто угодно подпишет
    # себе админский токен. Вне LOCAL/TEST это фатально, поэтому fail-fast.
    if cfg.auth.uses_dev_keys and cfg.env not in ("LOCAL", "TEST"):
        raise click.ClickException(
            f"Refusing to start in ENV={cfg.env} with the development JWT keys bundled in the repo. "
            f"Generate a keypair (make keys) and pass AUTH__PRIVATE_KEY_PATH / AUTH__PUBLIC_KEY_PATH "
            f"(or AUTH__PRIVATE_KEY / AUTH__PUBLIC_KEY).",
        )
    if cfg.auth.uses_dev_keys:
        logger.warning("Using development JWT keys from the repository — never do this outside local dev")

    if cfg.logs.sentry.enabled:
        sentry_sdk.init(
            dsn=cfg.logs.sentry.dsn,
            integrations=cfg.logs.sentry.integrations,
            environment=cfg.env,
        )
    try:
        asyncio.run(web.start(host=cfg.app.host, port=cfg.app.port, logs_config=cfg.logs.config.get_logging_config()))
    except KeyboardInterrupt:
        logger.critical("Server stopped by user")


@cli.command(short_help="bootstrap owner")
@click.option("--login", "login", default=None, help="Логин овнера (default: AUTH__OWNER_LOGIN / 'admin')")
@click.option("--password", "password", default=None, help="Пароль овнера (default: AUTH__OWNER_PASSWORD)")
@click.option(
    "--adopt-existing",
    is_flag=True,
    default=False,
    help="Выдать OWNER существующей учётке с таким логином (её пароль будет перезаписан)",
)
def bootstrap_owner(login: str | None, password: str | None, adopt_existing: bool) -> None:
    """
    Идемпотентная инициализация сервиса: системный client_app `auth-admin`
    + identity с password credential + grant OWNER.
    """
    from web.app import app

    login = login or cfg.auth.owner_login
    password = password or cfg.auth.owner_password
    if not password:
        if cfg.env != "LOCAL":
            raise click.ClickException(
                "Owner password is required outside LOCAL env: set AUTH__OWNER_PASSWORD or pass --password",
            )
        password = "admin"  # noqa: S105 — дефолт только для LOCAL

    error: str | None = None

    async def do() -> None:
        nonlocal error
        await app.start()
        try:
            result = await app.bootstrap_owner(login, password, adopt_existing=adopt_existing)
            if result["created"]:
                logger.info("Owner bootstrapped: identity %s, login '%s'", result["identity_id"], login)
            else:
                logger.info("Owner already bootstrapped: identity %s", result["identity_id"])
        except ValueError as e:
            error = str(e)
        finally:
            await app.stop()

    try:
        asyncio.run(do())
    except KeyboardInterrupt:
        logger.critical("Command stopped by user")
    if error:
        raise click.ClickException(error)


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
