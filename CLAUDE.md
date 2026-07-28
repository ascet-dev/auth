# Auth Service

Универсальный сервис аутентификации. Управляет identity, credentials, sessions. Ничего не знает о бизнес-логике.

## Структура

```
├── models/              # SQLModel-модели (схема auth в PostgreSQL)
│   ├── base.py          # BaseModel: id (UUID v7), created, updated, archived
│   ├── enums.py         # IdentityStatus, CredentialType, SessionStatus, OtpChannel, AuthClientType, AdminRole
│   ├── identity.py      # AuthIdentity (tenant_id, status)
│   ├── credential.py    # Credential (identity_id, type, identifier, provider, secret_hash, external_subject_id, meta)
│   ├── session.py       # Session (identity_id, client_app_id, refresh_token_hash, status)
│   ├── client_app.py    # ClientApp (key, type, TTLs, allowed URIs/scopes)
│   ├── connector.py     # AuthConnector — экземпляр способа входа (key, type, enabled, settings JSONB)
│   ├── client_app_connector.py  # M2M: какие коннекторы разрешены приложению
│   ├── otp_challenge.py # AuthOtpChallenge (channel, destination, code_hash, expires_at)
│   ├── logins.py        # Login (method, identifier, success, ip, user_agent) — аудит
│   ├── admin_grant.py   # AuthAdminGrant (identity_id, role, granted_by) — админские права
│   └── identity_external_link.py  # Маппинг identity → внешняя система
├── services/
│   ├── service.py       # App (BaseApp) — ВСЯ бизнес-логика: login_by_*, resolve_auth_connector, sessions, JWT, bootstrap_owner, гранты
│   ├── repositories.py  # DAO (PostgresAccessLayer + 10 TableDescriptor)
│   ├── password_service.py  # Argon2id хеширование
│   ├── login_attempt_logger.py  # Async context manager для аудита логинов
│   └── components/
│       ├── current_identity.py  # REQUEST-scoped: загружает identity из JWT sub, проверяет ACTIVE
│       └── current_admin.py     # REQUEST-scoped: identity ACTIVE + активный админский грант (мгновенный отзыв)
├── web/
│   ├── app.py           # WebApp + Route-ы + mount SPA (/admin/ui) + startup-проверка bootstrap
│   ├── auth.py          # jwt (payload=Client) и admin_jwt (payload=AdminClient c обязательным role)
│   └── endpoints/
│       ├── schemas.py   # Pydantic request/response модели пользовательского API
│       ├── auth_password.py  # RegisterPassword, LoginByPassword
│       ├── auth_oauth.py     # StartOauthFlow, LoginByOauth
│       ├── auth_tma.py       # LoginByTMA (Telegram Mini App)
│       ├── auth_otp.py       # SendOtp, LoginByOtp (TODO)
│       ├── sessions.py       # RefreshSession, Logout, ListSessions, RevokeSession, RevokeAllSessions
│       ├── credentials.py    # LinkPassword, LinkOtp, LinkOauth, RevokeCredential (TODO)
│       ├── identity.py       # CreateIdentity, GetIdentity, DeleteIdentity (TODO)
│       ├── external.py       # LinkExternalUser (TODO)
│       ├── maintenance.py    # CleanupSessions, CleanupOtp (TODO)
│       ├── default.py        # Liveness, Readiness
│       ├── admin_auth.py     # AdminLogin, AdminRefreshSession, AdminMe
│       └── admin/            # Admin CRUD API (auth = admin_jwt)
│           ├── base.py       # AdminEndpoint (guard+роли), generic AdminList/Get/Create/Update/Archive, Conflict(409)
│           ├── schemas.py    # Search/Read/Write модели (read-модели явные — секреты маскируются)
│           ├── client_apps.py, identities.py, sessions.py, logins.py, grants.py
│           └── connectors.py # CRUD /admin/connectors + маппинг /admin/client-apps/{id}/connectors
├── frontend/            # Админский SPA: React + Vite + TS + Mantine + TanStack Query
│   ├── src/api/         # client.ts (access в памяти, refresh в localStorage, авто-refresh на 401), types.ts
│   ├── src/auth/        # AuthContext (login/logout/me/role)
│   ├── src/components/  # Layout, RequireAuth, DataTable
│   └── src/pages/       # Login, ClientApps, Connectors, Identities(+Detail), Sessions, Logins, Grants
├── settings/
│   ├── settings.py      # CFG — корневой конфиг, объединяет подмодули
│   ├── auth.py          # JWT (RS256, TTLs, ключи), Telegram, owner_login/owner_password (bootstrap)
│   ├── postgres.py      # DSN, pool, schema_name="auth"
│   ├── app.py           # host, port, CORS
│   └── env.py, doc.py, logs.py, s3.py, sentry.py, telemetry.py
├── alembic/             # Миграции (env.py использует DAO.meta, сам создаёт схему auth)
│   └── versions/        # 0001 initial, 0002 admin grants (+partial unique index)
├── tests/               # pytest против реального PG (auth_test): conftest пересоздаёт БД + alembic
├── data/init_data.sql   # Тестовые данные: только test-app client (админ — через bootstrap-owner)
├── manage.py            # CLI: start-web, apply-sql, seed-data, bootstrap-owner
├── Makefile             # make init (turnkey docker) / dev-init / run / dev-ui / test / check / db-*
└── docker-compose.yml   # postgres, minio, migrations, bootstrap (owner), backend (API + SPA)
```

## Turnkey-запуск

`make init` — полный стек в docker: postgres → миграции → сид → `bootstrap-owner` → backend (API + SPA).
Админка: http://localhost:8003/admin/ui/ (логин `admin/admin`, переопределяется `OWNER_LOGIN`/`OWNER_PASSWORD`).
Dev-флоу: `make dev-init` → `make run` (API :8002) + `make dev-ui` (Vite :5173 с proxy).

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

- Access token: RS256 JWT, 1 мин, payload: `{sub, iat, exp, type, tenant?, role?}`
  (`role` добавляется только для сессий системного client_app `auth-admin`)
- Refresh token: opaque (secrets.token_urlsafe(64)), в БД хранится SHA-256 hash
- Ротация: при каждом refresh выдаётся новый refresh token, старый инвалидируется

### Админка (auth-сервис-операторы)

- Админ = обычная `AuthIdentity` + password `Credential` + явный грант в `auth_admin_grants`
  (роли `OWNER`/`ADMIN`; partial unique index: один активный грант на identity)
- Сессии — в общей таблице, но под системным client_app `auth-admin` (создаётся bootstrap-ом)
- Bootstrap: `python manage.py bootstrap-owner` (идемпотентно; вне LOCAL пароль обязателен —
  `AUTH__OWNER_PASSWORD`). Если логин уже занят — отказ (регистрация публична, иначе OWNER
  ушёл бы чужой учётке); `--adopt-existing` выдаёт грант ей же со сбросом пароля.
  При старте web без OWNER-а — ERROR в лог, старт не блокируется
- Системный client_app `auth-admin` неизменяем через API (архивация/смена TTL ломала бы
  вход в админку для всех), `key` client_app-ов уникален
- Guard: `auth = admin_jwt` (токен без `role` → 401) + `CurrentAdmin` перепроверяет грант в БД
  (отзыв действует сразу); refresh с отозванным грантом ревокает сессию
- CRUD-эндпоинты: наследовать generic-базы из `web/endpoints/admin/base.py`
  (`AdminList/Get/Create/Update/Archive`, `require_role = AdminRole.OWNER` для owner-only)

## Реализованные auth-методы

| Метод | Тип credential | Как ищет identity | Файл |
|-------|---------------|-------------------|------|
| Password | `PASSWORD` | `search(identifier=login, type=PASSWORD)` | service.py:login_by_password |
| OAuth 2.0 | `OAUTH` | `search(provider=connector_key, external_subject_id=sub)` | service.py:login_by_oauth |
| TMA | `TMA` | `search(type=TMA, external_subject_id=telegram_id)` | service.py:login_by_tma |
| Admin | `PASSWORD` | `_verify_password_credential` + активный грант | service.py:login_by_admin |

Паттерн одинаковый: найти credential → получить identity_id → создать сессию → вернуть JWT.

### Коннекторы — экземпляры способов входа

Модель как в Auth0 (connections): коннектор = именованный экземпляр метода,
одного типа может быть много (два TMA-бота, два Google-приложения, разные парольные политики).

- `auth_connectors`: `key` (слаг; для OAUTH это параметр `provider` в `/auth/oauth/*`),
  `type` (PASSWORD/OTP/TMA/OAUTH), `enabled`, `settings JSONB`:
  PASSWORD — `max_failed_attempts`, `lockout_minutes`, `allow_registration`;
  TMA — `bot_token` (write-only), `auth_date_max_age`; OAUTH — `client_id`,
  `client_secret` (write-only), `auth_url`, `token_url`, `jwks_url`, `userinfo_url`.
- Привязка к приложениям — M2M `auth_client_app_connectors`; нет привязок = все включённые.
  На приложение — максимум один PASSWORD-коннектор.
- Резолв — `App.resolve_auth_connector(type, client_app_id, key)` в начале login-флоу:
  key задан → он; один доступный → он; несколько → клиент передаёт `connector` (TMA) /
  `provider` (OAuth); коннекторов типа нет вообще → встроенные дефолты
  (PASSWORD — политика из констант, TMA — env bot token). `login_by_admin` резолвер
  НЕ использует: выключив пароль, нельзя отрезать себе админку.
- Identity-линковка глобальная: один telegram_id = одна identity через любых ботов
  (яндекс-модель: много приложений — один аккаунт). `credential.provider` хранит key
  коннектора — точка будущей изоляции, если понадобится.

## Конфигурация

Pydantic-settings, разделитель `__`, prefix отсутствует:

```bash
PG__CONNECTION__DSN=postgresql://postgres:postgres@localhost:5432/auth
AUTH__TELEGRAM_BOT_TOKEN=123456:ABC-DEF...  # для TMA
AUTH__TMA_AUTH_DATE_MAX_AGE=300             # максимальный возраст initData в секундах
AUTH__PUBLIC_KEY="..."   # PEM public key
AUTH__PRIVATE_KEY="..."  # PEM private key (не хранить в репо)
```

Тестовые RSA-ключи зашиты в `settings/auth.py` **только для LOCAL/TEST**: они лежат в
публичном репозитории, поэтому вне этих окружений `manage.py start-web` отказывается
стартовать. Ключи для остальных окружений: `make keys` генерирует пару в `secrets/`
(gitignored, монтируется в контейнер), пути — `AUTH__PRIVATE_KEY_PATH` /
`AUTH__PUBLIC_KEY_PATH`; можно и содержимым через `AUTH__PRIVATE_KEY` / `AUTH__PUBLIC_KEY`.

## Соглашения

- Длина строки: 120 символов
- Линтер/форматтер: **ruff** (основной), **black** (120, py311)
- Типизация: **mypy** strict для основного кода
- Классы: PascalCase, функции: snake_case, константы: UPPER_CASE
- Комментарии на русском допустимы
- Soft delete через `archived` (не физическое удаление)
- UUID v7 для всех PK (server_default `uuidv7()` в БД, PG 18+)
- Все эндпоинты регистрируются в `web/app.py` как `Route(...)`
- Enum-значения только добавляются, никогда не удаляются
- Автолинковка credentials запрещена (credential привязывается к identity только явно)

## Команды

```bash
make init             # turnkey: ключи + весь стек в docker, админка на :8003/admin/ui/
make keys             # сгенерировать JWT-пару в secrets/ (идемпотентно)
make dev-init         # dev-окружение: deps + PG в docker + миграции + bootstrap-owner
make run              # API локально на http://localhost:8002
make dev-ui           # Vite dev server фронта на :5173 (proxy на :8002)
make build-ui         # собрать SPA в frontend/dist (для локального make run с UI)
make test             # pytest (поднимает postgres в docker, БД auth_test)
make check            # ruff + mypy + bandit
make db-upgrade       # применить Alembic-миграции
make db-migrate message="..."  # создать новую миграцию
uv run python manage.py bootstrap-owner  # идемпотентный bootstrap OWNER-а
```
