# Auth Service

Универсальный сервис аутентификации. Управляет identity, credentials и sessions. Ничего не знает о бизнес-логике внешних систем.

## Что делает

- Регистрирует и аутентифицирует пользователей (password, OAuth 2.0, Telegram Mini App)
- Выдаёт JWT access tokens (RS256, 1 мин) и refresh tokens (opaque, 30 дней, с ротацией)
- Управляет сессиями (создание, refresh, отзыв, list)
- Логирует все попытки входа (аудит)
- Защищает от brute-force (lockout после 5 неудач на 30 мин)
- Хранит только auth-данные: identity + credentials + sessions. Профили, бизнес-данные — в других сервисах.

## Модель данных

```
auth_identities              — пользователь (абстрактный аккаунт)
  └── auth_credentials       — способы входа (1 identity → N credentials)
        type: PASSWORD         email/username + Argon2id hash
        type: OAUTH            Google, VK, etc. (authorization code flow)
        type: TMA              Telegram Mini App (initData HMAC verify)
        type: OTP_*            SMS/email/WhatsApp/Telegram (частично)
        type: API_KEY          (зарезервирован)
  └── auth_sessions          — активные сессии (refresh token hash)

auth_client_apps             — приложения-клиенты (TTL, redirect URI, scopes)
auth_oauth_providers         — конфигурация OAuth-провайдеров
auth_otp_challenges          — OTP-коды (временные)
auth_logins                  — аудит всех попыток входа
auth_identity_external_links — маппинг identity → внешние системы
```

Все таблицы в схеме `auth`. Soft delete через поле `archived`. UUID v4 для PK.

## API

### Аутентификация

| Метод | Эндпоинт | Описание | Статус |
|-------|----------|----------|--------|
| POST | `/auth/register/password` | Регистрация (email/username + пароль) | done |
| POST | `/auth/login/password` | Вход по паролю | done |
| POST | `/auth/oauth/start` | Начать OAuth flow (получить redirect URL) | done |
| POST | `/auth/oauth/login` | Завершить OAuth flow (обменять code на сессию) | done |
| POST | `/auth/tma/login` | Вход через Telegram Mini App initData | done |
| POST | `/auth/otp/send` | Отправить OTP код | todo |
| POST | `/auth/otp/login` | Вход по OTP коду | todo |

### Сессии

| Метод | Эндпоинт | Описание | Статус |
|-------|----------|----------|--------|
| POST | `/auth/session/refresh` | Ротация refresh token | done |
| POST | `/auth/session/logout` | Отозвать сессию | done |
| GET | `/auth/sessions` | Список активных сессий | done |
| DELETE | `/auth/sessions/{id}` | Отозвать конкретную сессию | done |
| POST | `/auth/sessions/revoke-all` | Отозвать все сессии | done |

### Identity и credentials

| Метод | Эндпоинт | Описание | Статус |
|-------|----------|----------|--------|
| POST | `/auth/identity` | Создать identity | todo |
| GET | `/auth/identity` | Получить identity | todo |
| DELETE | `/auth/identity` | Удалить identity | todo |
| POST | `/auth/credentials/*/link` | Привязать credential | todo |
| POST | `/auth/credentials/revoke` | Отозвать credential | todo |
| POST | `/auth/external/link` | Маппинг на внешнюю систему | todo |

### Health

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/readiness` | Готовность (PG, S3) |
| GET | `/liveness` | Жив ли сервер |

## Флоу аутентификации

### Password

```
Client → POST /auth/register/password {login, password}
       ← {identity_id, status}

Client → POST /auth/login/password {login, password, client_app_id}
       ← {session, access_token, refresh_token}
```

### OAuth 2.0

```
Client → POST /auth/oauth/start {provider, redirect_uri}
       ← {redirect_url}

Client → (redirect to provider → user authorizes → redirect back with code)

Client → POST /auth/oauth/login {provider, code, redirect_uri, client_app_id}
       ← {session, access_token, refresh_token}
```

### Telegram Mini App (TMA)

```
TMA    → Telegram передаёт initData (подписан HMAC-SHA256 ботовым токеном)
Client → POST /auth/tma/login {init_data, client_app_id}
         1. Парсит initData (query string)
         2. Верифицирует HMAC-SHA256 подпись
         3. Проверяет свежесть auth_date (дефолт 5 мин)
         4. Ищет credential (type=TMA, external_subject_id=telegram_id)
         5. Если нет → создаёт identity + credential
         6. Создаёт сессию
       ← {session, access_token, refresh_token}
```

### Refresh

```
Client → POST /auth/session/refresh {refresh_token, client_app_id}
         1. Находит сессию по hash(refresh_token)
         2. Проверяет expiry
         3. Ротация: новый refresh_token, новый access_token
       ← {session, access_token, refresh_token}
```

## JWT

- Алгоритм: **RS256** (RSA + SHA-256)
- Access token: 1 минута, JWT, подписан private key
- Refresh token: 30 дней (настраивается per client_app), opaque token, в БД хранится только SHA-256 hash
- Payload: `{sub: identity_id, iat, exp, type: "access", tenant?}`

Внешние сервисы валидируют access token публичным ключом без обращения к auth-сервису.

## Запуск

### Локально

```bash
# 1. Зависимости
uv sync

# 2. Инфраструктура (PostgreSQL + MinIO)
docker-compose up -d postgres minio minio_init

# 3. Миграции
make db-upgrade FORCE=true

# 4. Тестовые данные (admin user + test client_app)
make data-migration FORCE=true

# 5. Запуск
make run
# → http://localhost:8002
```

### Docker Compose (всё вместе)

```bash
docker-compose up -d
# → http://localhost:8003
```

### Полная инициализация с нуля

```bash
make init
# Установит deps, создаст .env, запустит инфру, применит миграции
```

## Конфигурация

Через переменные окружения (pydantic-settings, разделитель `__`):

```bash
# PostgreSQL
PG__CONNECTION__DSN=postgresql://postgres:postgres@localhost:5432/auth

# JWT (обязательно заменить в продакшене!)
AUTH__ALGORITHMS=["RS256"]
AUTH__ACCESS_TOKEN_LIFETIME=60        # секунды
AUTH__REFRESH_TOKEN_LIFETIME=2592000  # 30 дней
AUTH__PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n..."
AUTH__PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."

# Telegram Mini App
AUTH__TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
AUTH__TMA_AUTH_DATE_MAX_AGE=300       # секунды, дефолт 5 мин

# Сервер
APP__HOST=0.0.0.0
APP__PORT=8002

# Окружение
ENV=LOCAL  # LOCAL | COMPOSE | PRODUCTION
```

В `LOCAL` окружении читается файл `.env`. В `COMPOSE` / `PRODUCTION` — только env-переменные.

## Тестовые данные

`data/init_data.sql` создаёт:
- `client_app` с ключом `test-app` (PUBLIC, access 15 мин, refresh 30 дней)
- `admin` пользователь (password: `admin`)

## Команды

```bash
make run              # запуск сервера
make test             # тесты
make check            # lint + format + mypy + bandit
make init             # полная инициализация
make docker-run       # docker-compose up
make db-migrate message="..."  # новая миграция Alembic
make db-upgrade       # применить миграции
make data-migration   # применить data/init_data.sql
make clean            # очистить временные файлы
make kill-server      # убить сервер на порту
```

## Стек

- **Python** 3.12, **uv**
- **adc-webkit** (async web, поверх aiohttp), **adc-appkit** (DI, lifecycle)
- **adc-aiopg** (async PostgreSQL), **SQLModel** (ORM)
- **Alembic** (миграции), **Pydantic Settings** (конфигурация)
- **python-jose** (JWT RS256), **passlib[argon2]** (пароли)
- **PostgreSQL** 15, **MinIO** (S3)
- **Docker** + **Docker Compose**
