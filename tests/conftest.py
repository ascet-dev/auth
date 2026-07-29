import os

# Env ДО любых импортов проекта: cfg вычисляется на import-time.
# ENV != LOCAL → .env не подгружается, конфигурация детерминирована.
os.environ.setdefault("ENV", "TEST")
os.environ.setdefault("PG__CONNECTION__DSN", "postgresql://postgres:postgres@localhost:5432/auth_test")


def _generate_test_keys() -> None:
    """Эфемерная пара на прогон: захардкоженных ключей в репозитории больше нет."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    os.environ.setdefault(
        "AUTH__PRIVATE_KEY",
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
    )
    os.environ.setdefault(
        "AUTH__PUBLIC_KEY",
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )


_generate_test_keys()

import subprocess  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

import httpx  # noqa: E402
import psycopg2  # noqa: E402
import pytest  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402

TEST_DSN = os.environ["PG__CONNECTION__DSN"]

# Порядок не важен: TRUNCATE ... CASCADE
ALL_TABLES = ", ".join(
    f"auth.{t}"
    for t in (
        "auth_logins",
        "auth_sessions",
        "auth_otp_challenges",
        "auth_admin_grants",
        "auth_client_app_connectors",
        "auth_connectors",
        "auth_credentials",
        "auth_identity_external_links",
        "auth_identities",
        "auth_client_apps",
    )
)


@pytest.fixture(scope="session")
def _test_database():
    """Пересоздаёт тестовую БД и накатывает миграции (один раз за сессию)."""
    parsed = urlparse(TEST_DSN)
    db_name = parsed.path.lstrip("/")

    # Ниже DROP DATABASE ... WITH (FORCE). Если PG__CONNECTION__DSN экспортирован
    # в шелле, setdefault выше его не перебьёт — и снесёт дев-базу.
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against '{db_name}': the test database name must end with '_test'. "
            f"Unset PG__CONNECTION__DSN or point it at a test database.",
        )

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()

    # Через console-script: локальная директория alembic/ шадоуит одноимённый пакет
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=os.environ.copy())  # noqa: S607


@pytest.fixture(scope="session")
async def web_app(_test_database):
    from web.app import web

    async with LifespanManager(web.web):
        yield web


@pytest.fixture(scope="session")
async def app(web_app):
    return web_app.web.state.app


@pytest.fixture(scope="session")
async def client(web_app):
    transport = httpx.ASGITransport(app=web_app.web)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def clean_db(app):
    """Чистая БД перед каждым тестом."""
    await app.pg.execute(f"TRUNCATE {ALL_TABLES} CASCADE")


@pytest.fixture
async def test_client_app(app, clean_db):
    """Пользовательский client_app (аналог test-app из init_data.sql)."""
    from models.enums import AuthClientType

    return await app.dao.client_apps.create(
        key="test-app",
        name="Test Application",
        type=AuthClientType.PUBLIC,
        allowed_redirect_uris=[],
        allowed_scopes=[],
        access_token_ttl_sec=900,
        refresh_token_ttl_sec=2592000,
    )


@pytest.fixture
async def owner(app, clean_db):
    """Bootstrap овнера admin/admin, возвращает результат bootstrap."""
    return await app.bootstrap_owner("admin", "admin")


@pytest.fixture
async def owner_tokens(client, owner):
    """Логин овнера, возвращает {session, access_token, refresh_token}."""
    resp = await client.post("/admin/auth/login", json={"login": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.text
    return resp.json()
