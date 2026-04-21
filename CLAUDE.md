# Auth Service

## Stack

- **Python** 3.12 (pyproject.toml requires >=3.11, Docker image uses 3.12-slim-bookworm)
- **adc-webkit** — async web framework (поверх aiohttp)
- **adc-appkit** — компонентная система и DI
- **adc-aiopg** — async PostgreSQL клиент
- **adc-aios3** — async S3 клиент
- **adc-logger** — структурированное логирование
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **Alembic** — миграции базы данных
- **Pydantic Settings** — конфигурация через env-переменные
- **python-jose** — JWT (RS256)
- **passlib[argon2]** — хеширование паролей (Argon2id)
- **click** — CLI (manage.py)
- **uvloop** — event loop
- **sentry-sdk** — мониторинг ошибок
- **uv** — пакетный менеджер (замена pip/poetry)

## Dev-инструменты

- **ruff** — линтер и форматтер (line-length: 120)
- **black** — форматирование (line-length: 120, target: py311)
- **isort** — сортировка импортов (profile: black)
- **mypy** — строгая типизация (disallow_untyped_defs: true)
- **bandit** — security-сканер
- **pre-commit** — git-хуки
- **pytest** + pytest-asyncio, pytest-cov, pytest-xdist, pytest-mock

## Структура проекта

```
├── models/          # SQLModel-модели (ORM + Pydantic)
│   ├── base.py      # BaseModel: id (UUID), created, updated, archived
│   ├── enums.py     # Enum-ы статусов и типов
│   └── *.py         # Таблицы: identity, credential, session, client_app, ...
├── services/        # Бизнес-логика
│   ├── service.py   # Основной App-класс со всей логикой
│   ├── repositories.py  # DAO (PostgresAccessLayer + TableDescriptor)
│   ├── password_service.py  # Argon2 хеширование
│   ├── schemas.py
│   └── components/  # REQUEST-scoped компоненты (CurrentIdentity)
├── web/             # HTTP-слой
│   ├── app.py       # WebApp: CORS, маршруты (Route)
│   ├── auth.py      # JWT-конфигурация (RS256)
│   └── endpoints/   # Эндпоинты (JsonEndpoint)
│       ├── schemas.py  # Pydantic request/response схемы
│       └── *.py     # auth_password, auth_otp, auth_oauth, sessions, ...
├── settings/        # Конфигурация (pydantic-settings)
│   ├── settings.py  # CFG: объединяет все подмодули
│   ├── app.py       # host, port, CORS
│   ├── postgres.py  # PG-подключение
│   ├── auth.py      # JWT ключи и TTL
│   ├── s3.py, logs.py, sentry.py, telemetry.py, doc.py
│   └── env.py       # ENV=LOCAL|COMPOSE|PRODUCTION
├── alembic/         # Миграции
├── data/            # SQL-фикстуры (init_data.sql)
├── manage.py        # CLI: start-web, apply-sql, seed-data
├── Makefile         # make run, make test, make check, make init, ...
├── Dockerfile       # Multi-stage: base → uv-setup → development/production
├── docker-compose.yml  # postgres, minio, migrations, backend
└── pyproject.toml   # Зависимости + конфиги ruff/mypy/pytest/black/isort/bandit
```

## Архитектурные паттерны

### Компонентная система (adc-appkit)
```python
class App(BaseApp):
    pg = component(PG, config_key="pg")
    dao: DAO = component(create_component(DAO), dependencies={"pool": "pg"})
    password_service = PasswordService()
```

### DAO (Data Access Layer)
```python
class DAO(PostgresAccessLayer, metadata=m.base.meta):
    identities = TableDescriptor[AuthIdentity](...)
    credentials = TableDescriptor[Credential](...)
    sessions = TableDescriptor[Session](...)
```
Операции: `dao.table.create(...)`, `dao.table.search(...)`, `dao.table.update_by_id(...)`, `dao.table.delete_by_id(...)`

### Эндпоинты
```python
class MyEndpoint(JsonEndpoint):
    doc = Doc(tags=[...], summary="...")
    auth = jwt           # опционально — защищенный эндпоинт
    body = MyRequest     # Pydantic-модель запроса
    response = Response(MyResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        ...
```

### Request Scope для авторизации
```python
async with app.request_scope({"current_identity": {"sub": identity_id, "dao": app.dao}}):
    identity = await app.current_identity.get()
```

### Context Manager для side effects
```python
async with app.log_login_attempt(method=..., identifier=...) as logger:
    # логика аутентификации
    logger.set(identity_id=..., credential_id=..., success=True)
```

## База данных

PostgreSQL 15, схема `auth`. Таблицы:
- `auth_identities` — пользователи (tenant_id, status)
- `auth_credentials` — способы входа (password/OTP/OAuth)
- `auth_sessions` — сессии с refresh token hash
- `auth_client_apps` — OAuth-клиенты
- `auth_oauth_providers` — провайдеры OAuth
- `auth_otp_challenges` — OTP-коды
- `auth_identity_external_links` — связи с внешними системами
- `auth_logins` — аудит попыток входа

Базовая модель: `id` (UUID v4), `created`, `updated`, `archived` (soft delete).

## Аутентификация

- **Password**: Argon2id, lockout после 5 неудач на 30 минут
- **OAuth 2.0**: authorization code flow, JWKS/userinfo валидация
- **OTP**: SMS/email/WhatsApp/Telegram (частично реализовано)
- **JWT**: RS256, access token 1 мин, refresh token 30 дней, ротация при refresh

## Команды

```bash
make run              # запуск сервера
make test             # тесты
make check            # lint + format + mypy + bandit
make init             # полная инициализация (deps + hooks + infra + migrations)
make docker-run       # docker-compose up
make db-migrate message="..."  # новая миграция
make db-upgrade       # применить миграции
```

## Соглашения

- Длина строки: 120 символов
- Классы: PascalCase, функции: snake_case, константы: UPPER_CASE
- Комментарии и описания на русском языке допустимы
- Strict mypy для основного кода, ослабленный для моделей/тестов
- Soft delete через поле `archived` (не физическое удаление)
- UUID v4 для всех первичных ключей
- Все эндпоинты регистрируются в `web/app.py` как `Route(...)`
