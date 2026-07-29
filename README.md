# Auth Service

Универсальный сервис аутентификации. Управляет identity, credentials и sessions. Ничего не знает о бизнес-логике внешних систем.

## Быстрый старт

```bash
git clone git@github.com:ascet-dev/auth.git && cd auth
make init
```

Поднимется весь стек в docker: PostgreSQL → миграции → сид → bootstrap владельца → backend с API и админкой.

- Админка: **http://localhost:8003/admin/ui/** — логин `admin` / `admin`
- API-доки (Swagger): http://localhost:8003/doc

Креды владельца переопределяются: `OWNER_LOGIN=... OWNER_PASSWORD=... make init`.

Локальная разработка без docker-обвязки: `make dev-init` (deps, ключи, PG в docker, миграции, bootstrap),
затем `make run` (API на :8002) и `make dev-ui` (Vite с proxy на :5173).

## Как подключить своё приложение

Полный путь от чистого инстанса до полученных токенов.

### 1. Создайте client app

Админка → **Client Apps** → New client app.

- `key` — логический идентификатор аудитории (`my-web`, `my-mobile`), менять потом нельзя
- `Access token TTL` / `Refresh token TTL` — время жизни токенов
- `Allowed redirect URIs` — куда OAuth-провайдер вернёт пользователя (нужно только для OAuth)
- `Connectors` — какие способы входа разрешены этому приложению; **пусто = все включённые**

Скопируйте `id` приложения (колонка ID) — он передаётся в каждый login-запрос как `client_app_id`.

### 2. Настройте способ входа (коннектор)

Админка → **Connectors** → New connector. Коннектор — это именованный экземпляр способа входа,
их может быть много одного типа: два телеграм-бота, два OAuth-приложения, разные парольные политики.

| Тип | Что заполнить | Где взять |
|-----|---------------|-----------|
| `PASSWORD` | `max_failed_attempts`, `lockout_minutes`, `allow_registration` | — |
| `TMA` | `bot_token`, `auth_date_max_age` | @BotFather |
| `OAUTH` | `client_id`, `client_secret`, `auth_url`, `token_url`, `jwks_url`, `userinfo_url` | консоль провайдера (Google Cloud, GitHub OAuth Apps, …) |
| `OTP` | — | не реализован |

Если ни одного коннектора нужного типа нет, работают встроенные дефолты: пароль — с политикой
5 попыток / 30 минут, TMA — с токеном из `AUTH__TELEGRAM_BOT_TOKEN`.

Затем привяжите коннекторы к приложению (Client Apps → Edit → Connectors).

### 3. Аутентифицируйте пользователя

`client_app_id` ниже — id из шага 1.

**Пароль.** Регистрация и вход:

```bash
curl -X POST http://localhost:8003/auth/register/password \
  -H 'Content-Type: application/json' \
  -d '{"login": "user@example.com", "password": "secret123"}'

curl -X POST http://localhost:8003/auth/login/password \
  -H 'Content-Type: application/json' \
  -d '{"login": "user@example.com", "password": "secret123", "client_app_id": "<CLIENT_APP_ID>"}'
```

Ответ у всех login-методов одинаковый:

```json
{
  "session": {"id": "...", "identity_id": "...", "status": "ACTIVE", "...": "..."},
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "0dQx...(opaque)"
}
```

**OAuth 2.0.** `provider` — это `key` вашего OAUTH-коннектора:

```bash
# 1) получить URL провайдера и увести туда пользователя
curl -X POST http://localhost:8003/auth/oauth/start \
  -H 'Content-Type: application/json' \
  -d '{"provider": "google-web", "redirect_uri": "https://myapp.com/callback"}'
# ← {"redirect_url": "https://accounts.google.com/o/oauth2/auth?..."}

# 2) провайдер вернёт пользователя на redirect_uri с ?code=...
curl -X POST http://localhost:8003/auth/oauth/login \
  -H 'Content-Type: application/json' \
  -d '{"provider": "google-web", "code": "<CODE>", "redirect_uri": "https://myapp.com/callback", "client_app_id": "<CLIENT_APP_ID>"}'
```

**Telegram Mini App.** `init_data` — сырая строка `Telegram.WebApp.initData`:

```bash
curl -X POST http://localhost:8003/auth/tma/login \
  -H 'Content-Type: application/json' \
  -d '{"init_data": "<initData>", "client_app_id": "<CLIENT_APP_ID>", "connector": "tma-shop-bot"}'
```

Поле `connector` обязательно, только если приложению привязано несколько TMA-коннекторов.

### 4. Держите сессию живой

Access-токен короткий (по умолчанию 1 минута) — клиент должен обновляться по refresh-токену:

```bash
curl -X POST http://localhost:8003/auth/session/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token": "<REFRESH>", "client_app_id": "<CLIENT_APP_ID>"}'
```

Refresh-токен одноразовый: каждый refresh выдаёт новый и инвалидирует старый. Если ответ 401 —
сессия закончилась (истекла, отозвана, пользователь заблокирован), нужно логиниться заново.

Выход: `POST /auth/session/logout` с `{session_id}` и заголовком `Authorization: Bearer <access>`.

### 5. Проверяйте токен на своей стороне

Access-токен — RS256 JWT, проверяется **публичным ключом без обращения к auth-сервису**:

```python
from jose import jwt
claims = jwt.decode(access_token, PUBLIC_KEY, algorithms=["RS256"])
# {"sub": "<identity_id>", "iat": ..., "exp": ..., "type": "access", "tenant": "...", "role": "OWNER"}
```

`sub` — id identity, стабильный идентификатор пользователя в вашей системе. `role` появляется только
в токенах админки. Публичный ключ — `secrets/jwt_public.pem` (или ваш из секрет-стора).

### Диагностика

- **Админка → Login Audit** — все попытки входа: метод, идентификатор, IP, успех/неуспех
- **Админка → Sessions** — активные сессии с возможностью отозвать
- **Админка → Identities** — карточка пользователя: credentials, внешние связи, админский грант
- Типовые ответы: `401 Invalid credentials` — неверный логин/пароль **или** блокировка после
  превышения попыток (снаружи неразличимо намеренно); `400 Auth method '...' is not allowed for
  this application` — коннектор не привязан к приложению; `400 ... is disabled` — коннектор выключен

## Модель данных

```
auth_identities              — пользователь (абстрактный аккаунт)
  └── auth_credentials       — способы входа (1 identity → N credentials)
        type: PASSWORD         email/username + Argon2id hash
        type: OAUTH            Google, GitHub, … (authorization code flow)
        type: TMA              Telegram Mini App (initData HMAC verify)
        type: OTP_*            SMS/email/WhatsApp/Telegram (не реализовано)
        type: API_KEY          (зарезервирован)
  └── auth_sessions          — активные сессии (refresh token hash)

auth_client_apps             — приложения-клиенты (TTL, redirect URI, scopes)
  └── auth_client_app_connectors — какие способы входа разрешены приложению (M2M)
auth_connectors              — экземпляры способов входа (bot token, OAuth-креды, парольная политика)
auth_admin_grants            — админские права на identity (OWNER | ADMIN)
auth_otp_challenges          — OTP-коды (временные)
auth_logins                  — аудит всех попыток входа
auth_identity_external_links — маппинг identity → внешние системы
```

Все таблицы в схеме `auth`. Soft delete через поле `archived`. UUID v7 для PK (PostgreSQL 18+).

## API

### Аутентификация

| Метод | Эндпоинт | Описание | Статус |
|-------|----------|----------|--------|
| POST | `/auth/register/password` | Регистрация (email/username + пароль) | done |
| POST | `/auth/login/password` | Вход по паролю | done |
| POST | `/auth/oauth/start` | Начать OAuth flow (получить redirect URL) | done |
| POST | `/auth/oauth/login` | Завершить OAuth flow (обменять code на сессию) | done |
| POST | `/auth/tma/login` | Вход через Telegram Mini App initData | done |
| POST | `/auth/otp/send`, `/auth/otp/login` | OTP | todo |

### Сессии

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/auth/session/refresh` | Ротация refresh token |
| POST | `/auth/session/logout` | Отозвать сессию |
| GET | `/auth/sessions` | Список активных сессий |
| DELETE | `/auth/sessions/{id}` | Отозвать конкретную сессию |
| POST | `/auth/sessions/revoke-all` | Отозвать все сессии |

### Админский API (`auth = admin_jwt`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/admin/auth/login`, `/admin/auth/refresh`, GET `/admin/auth/me` | вход админа |
| GET/POST/PATCH/DELETE | `/admin/client-apps[/{id}]` | приложения |
| GET/PUT | `/admin/client-apps/{id}/connectors` | привязка коннекторов |
| GET/POST/PATCH/DELETE | `/admin/connectors[/{id}]` | способы входа |
| GET | `/admin/identities[/{id}]` | пользователи |
| GET, DELETE | `/admin/sessions[/{id}]` | сессии, ревокация |
| GET | `/admin/logins` | аудит входов |
| GET/POST/DELETE | `/admin/grants[/{id}]` | админские права (мутации — только OWNER) |

Health: `GET /liveness`, `GET /readiness`.

## JWT

- Алгоритм **RS256**; access — 1 минута, refresh — opaque, в БД только SHA-256 hash, ротация при каждом обновлении
- Payload: `{sub: identity_id, iat, exp, type: "access", tenant?, role?}` (`role` — только админские сессии)
- Ключи обязательны и дефолтов не имеют: `make keys` генерирует пару в `secrets/` (gitignored),
  пути передаются через `AUTH__PRIVATE_KEY_PATH` / `AUTH__PUBLIC_KEY_PATH`, содержимое — через
  `AUTH__PRIVATE_KEY` / `AUTH__PUBLIC_KEY`. Без ключей сервис не стартует.
  В проде ключи выдаёт секрет-стор платформы, `make keys` — только для локального стека.

## Админы сервиса

Админ — это обычная identity с паролем плюс явный грант (`OWNER` или `ADMIN`). Первый владелец
создаётся командой `python manage.py bootstrap-owner` (идемпотентно, вызывается в `make init`).
Если логин уже занят — команда откажет: используйте другой `AUTH__OWNER_LOGIN` или `--adopt-existing`
(выдаст грант существующей учётке и перезапишет её пароль).

Роль перечитывается из БД на каждом запросе, поэтому отзыв прав действует мгновенно, не дожидаясь
истечения токена. Системное приложение `auth-admin` неизменяемо через API.

## Конфигурация

Переменные окружения (pydantic-settings, разделитель `__`):

```bash
PG__CONNECTION__DSN=postgresql://postgres:postgres@localhost:5432/auth

AUTH__PRIVATE_KEY_PATH=secrets/jwt_private.pem   # или AUTH__PRIVATE_KEY с PEM
AUTH__PUBLIC_KEY_PATH=secrets/jwt_public.pem     # или AUTH__PUBLIC_KEY
AUTH__ACCESS_TOKEN_LIFETIME=60                   # секунды
AUTH__OWNER_LOGIN=admin                          # для bootstrap-owner
AUTH__OWNER_PASSWORD=...                         # вне LOCAL обязателен

AUTH__TELEGRAM_BOT_TOKEN=123456:ABC...           # fallback, если нет TMA-коннектора
AUTH__TMA_AUTH_DATE_MAX_AGE=300

APP__HOST=0.0.0.0
APP__PORT=8002
ENV=LOCAL                                        # в LOCAL читается .env
```

## Команды

```bash
make init             # turnkey: ключи + весь стек в docker
make dev-init         # dev-окружение (deps, ключи, PG в docker, миграции, bootstrap)
make keys             # сгенерировать JWT-пару в secrets/
make run              # API локально на :8002
make dev-ui           # Vite dev server админки на :5173
make build-ui         # собрать SPA в frontend/dist
make test             # pytest против PostgreSQL из docker
make check            # ruff + mypy + bandit
make db-upgrade       # применить миграции
make db-migrate message="..."   # новая миграция
make docker-logs      # логи стека
```

## Стек

- **Python** 3.12, **uv**
- **adc-webkit** (async web поверх Starlette), **adc-appkit** (DI, lifecycle), **adc-aiopg** (async PostgreSQL)
- **SQLModel** + **Alembic**, **Pydantic Settings**
- **python-jose** (JWT RS256), **passlib[argon2]**
- **PostgreSQL 18**, **MinIO** (S3)
- Админка: **React** + **Vite** + **TypeScript** + **Mantine** + **TanStack Query**
