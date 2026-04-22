# Auth Service

Универсальный сервис аутентификации. Управляет identity, credentials, sessions. Ничего не знает о бизнес-логике.

## Структура

```
├── models/              # SQLModel-модели (схема auth в PostgreSQL)
│   ├── base.py          # BaseModel: id (UUID v4), created, updated, archived
│   ├── enums.py         # IdentityStatus, CredentialType, SessionStatus, OtpChannel, AuthClientType
│   ├── identity.py      # AuthIdentity (tenant_id, status)
│   ├── credential.py    # Credential (identity_id, type, identifier, provider, secret_hash, external_subject_id, meta)
│   ├── session.py       # Session (identity_id, client_app_id, refresh_token_hash, status)
│   ├── client_app.py    # ClientApp (key, type, TTLs, allowed URIs/scopes)
│   ├── oauth_provider.py # AuthOauthProvider (name, client_id/secret, URLs, enabled)
│   ├── otp_challenge.py # AuthOtpChallenge (channel, destination, code_hash, expires_at)
│   ├── logins.py        # Login (method, identifier, success, ip, user_agent) — аудит
│   └── identity_external_link.py  # Маппинг identity → внешняя система
├── services/
│   ├── service.py       # App (BaseApp) — ВСЯ бизнес-логика: login_by_password, login_by_oauth, login_by_tma, sessions, JWT
│   ├── repositories.py  # DAO (PostgresAccessLayer + 8 TableDescriptor)
│   ├── password_service.py  # Argon2id хеширование
│   ├── login_attempt_logger.py  # Async context manager для аудита логинов
│   └── components/
│       └── current_identity.py  # REQUEST-scoped: загружает identity из JWT sub, проверяет ACTIVE
├── web/
│   ├── app.py           # WebApp + Route-ы + создание app
│   ├── auth.py          # JWT объект (RS256, public_key, payload_model=Client)
│   └── endpoints/
│       ├── schemas.py   # Все Pydantic request/response модели
│       ├── auth_password.py  # RegisterPassword, LoginByPassword
│       ├── auth_oauth.py     # StartOauthFlow, LoginByOauth
│       ├── auth_tma.py       # LoginByTMA (Telegram Mini App)
│       ├── auth_otp.py       # SendOtp, LoginByOtp (TODO)
│       ├── sessions.py       # RefreshSession, Logout, ListSessions, RevokeSession, RevokeAllSessions
│       ├── credentials.py    # LinkPassword, LinkOtp, LinkOauth, RevokeCredential (TODO)
│       ├── identity.py       # CreateIdentity, GetIdentity, DeleteIdentity (TODO)
│       ├── external.py       # LinkExternalUser (TODO)
│       ├── maintenance.py    # CleanupSessions, CleanupOtp (TODO)
│       └── default.py        # Liveness, Readiness
├── settings/
│   ├── settings.py      # CFG — корневой конфиг, объединяет подмодули
│   ├── auth.py          # JWT (RS256, TTLs, ключи), Telegram (bot_token, auth_date_max_age)
│   ├── postgres.py      # DSN, pool, schema_name="auth"
│   ├── app.py           # host, port, CORS
│   └── env.py, doc.py, logs.py, s3.py, sentry.py, telemetry.py
├── alembic/             # Миграции (env.py использует DAO.meta)
│   └── versions/        # Файлы миграций
├── data/init_data.sql   # Тестовые данные: test-app client + admin user
├── manage.py            # CLI: start-web, apply-sql
├── Makefile             # make run/test/check/init/db-upgrade/...
└── docker-compose.yml   # postgres, minio, migrations, backend
```

## Ключевые паттерны

### Как устроен App (services/service.py)

Единый класс `App(BaseApp)` содержит ВСЮ бизнес-логику. Компоненты подключаются через DI:

```python
class App(BaseApp):
    pg = component(PG, config_key="pg")
    dao: DAO = component(create_component(DAO), dependencies={"pool": "pg"})
    password_service = PasswordService()
    current_identity = component(CurrentIdentity, strategy=ComponentStrategy.REQUEST)
```

### Как писать эндпоинт

```python
class MyEndpoint(JsonEndpoint):
    doc = Doc(tags=["my_tag"], summary="Что делает")
    auth = jwt                    # если нужна авторизация (иначе убрать)
    body = MyRequest              # Pydantic-модель из schemas.py
    response = Response(MyResponse)

    async def execute(self, ctx: Ctx) -> dict:
        app: App = ctx.request.app.state.app
        # бизнес-логика через app.method(...)
        return {"key": "value"}
```

Регистрация: добавить в `web/app.py` → `Route("POST", "/path", MyEndpoint)` и в `web/endpoints/__init__.py`.

### Как работает аутентификация в эндпоинтах

- `auth = jwt` на эндпоинте → JWT валидируется, `sub` (identity_id) доступен
- Для доступа к текущей identity: `request_scope` → `app.current_identity`
- Для незащищённых эндпоинтов (login, register) — `auth` не указывается

### Как работает DAO

```python
# Создание
entity = await app.dao.credentials.create(type=CredentialType.TMA, ...)
# Поиск (kwargs — фильтры)
results = await app.dao.credentials.search(provider="google", archived=False, limit=1)
# Обновление
await app.dao.credentials.update_by_id(entity.id, last_used=now)
# По ID
entity = await app.dao.sessions.get_by_id(session_id)
# Массовое обновление
updated = await app.dao.sessions.update({"status": SessionStatus.REVOKED}, identity_id=id)
```

### Как работают enum-ы в БД

Enum-ы хранятся как PostgreSQL ENUM types (через `sqla_enum` из adc_aiopg):

```python
# В модели:
type: CredentialType = Field(default=CredentialType.PASSWORD, sa_column=sqla_enum(CredentialType).sa_column)
```

Имя PG-типа: CamelCase → snake_case (CredentialType → `auth.credential_type`).
Добавление нового значения — Alembic-миграция: `ALTER TYPE auth.credential_type ADD VALUE 'NEW_VALUE'`.
**Удалять значения из enum нельзя** (PostgreSQL ограничение).

### Аудит логинов

Все login-методы оборачиваются в `log_login_attempt`:

```python
async with self.log_login_attempt(method="tma", identifier=None, ip_address=ip, user_agent=ua) as logger:
    # логика аутентификации
    logger.set(identity_id=identity_id, credential_id=credential.id)
    return session, tokens
    # если вылетит exception — запишется success=False
```

### JWT токены

- Access token: RS256 JWT, 1 мин, payload: `{sub, iat, exp, type, tenant?}`
- Refresh token: opaque (secrets.token_urlsafe(64)), в БД хранится SHA-256 hash
- Ротация: при каждом refresh выдаётся новый refresh token, старый инвалидируется

## Реализованные auth-методы

| Метод | Тип credential | Как ищет identity | Файл |
|-------|---------------|-------------------|------|
| Password | `PASSWORD` | `search(identifier=login, type=PASSWORD)` | service.py:login_by_password |
| OAuth 2.0 | `OAUTH` | `search(provider=provider, external_subject_id=sub)` | service.py:login_by_oauth |
| TMA | `TMA` | `search(type=TMA, external_subject_id=telegram_id)` | service.py:login_by_tma |

Паттерн одинаковый: найти credential → получить identity_id → создать сессию → вернуть JWT.

## Конфигурация

Pydantic-settings, разделитель `__`, prefix отсутствует:

```bash
PG__CONNECTION__DSN=postgresql://postgres:postgres@localhost:5432/fitness
AUTH__TELEGRAM_BOT_TOKEN=123456:ABC-DEF...  # для TMA
AUTH__TMA_AUTH_DATE_MAX_AGE=300             # максимальный возраст initData в секундах
AUTH__PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n..."
AUTH__PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
```

Тестовые RSA-ключи зашиты в `settings/auth.py` для LOCAL-окружения. В продакшене — через env.

## Соглашения

- Длина строки: 120 символов
- Линтер/форматтер: **ruff** (основной), **black** (120, py311)
- Типизация: **mypy** strict для основного кода
- Классы: PascalCase, функции: snake_case, константы: UPPER_CASE
- Комментарии на русском допустимы
- Soft delete через `archived` (не физическое удаление)
- UUID v4 для всех PK (server_default в БД)
- Все эндпоинты регистрируются в `web/app.py` как `Route(...)`
- Enum-значения только добавляются, никогда не удаляются
- Автолинковка credentials запрещена (credential привязывается к identity только явно)

## Команды

```bash
make run              # сервер на http://localhost:8002
make test             # pytest
make check            # ruff + mypy + bandit
make init             # полная инициализация с нуля
make db-upgrade       # применить Alembic-миграции
make db-migrate message="..."  # создать новую миграцию
```
