# План: админская аутентификация

Статус: утверждён, в работе (2026-07-17)

## Контекст и цели

Нужна аутентификация для админов auth-сервиса (операторов, а не конечных пользователей):

1. Админская аутентификация (login + JWT с ролью).
2. При инициализации приложения создаётся админ с правами овнера.
3. Позже — API для CRUD-операций над приложениями, провайдерами и т.д. (только для админов).
4. Позже — UI для управления auth-сервисом (сессии, приложения).

## Зафиксированные решения

- Админ = обычная `AuthIdentity` + password `Credential` + **явный grant** в новой таблице
  `auth_admin_grants`. Роли: `OWNER` и `ADMIN`.
- Админские сессии — в общей таблице sessions, но через **системный ClientApp `auth-admin`**
  (создаётся при bootstrap, отдельные TTL, сегрегация сессий для будущего UI).
- Bootstrap — **явная CLI-команда** `manage.py bootstrap-owner`; при старте web — только проверка
  и `ERROR` в лог, если инициализация не проведена (старт не блокируем, пользовательский auth
  работает независимо).

Отвергнутые альтернативы:

- *Роль прямо на identity* — смешивает админство сервиса с универсальной таблицей пользователей,
  не масштабируется до гранулярных прав, нет аудита выдачи.
- *Отдельная таблица admin_users со своим auth-стеком* — дублирует пароли/lockout/сессии/аудит;
  оправдано только при жёстких compliance-требованиях.

## Этап 1 — Модель данных и миграция

1. `models/enums.py`: `AdminRole(StrEnum)` = `OWNER | ADMIN` → PG-тип `auth.admin_role`.
2. `models/admin_grant.py`: `AuthAdminGrant(BaseModel)`:
   - `identity_id` (FK → `auth_identities.id`)
   - `role: AdminRole`
   - `granted_by: UUID | None` (FK → identity; `NULL` = bootstrap) — аудит выдачи.
3. Уникальность: из-за soft delete обычный unique не подходит — **partial unique index**
   `(identity_id) WHERE archived = false` (в миграции руками, `postgresql_where`).
   Иначе после отзыва нельзя выдать грант повторно.
4. `services/repositories.py`: `admin_grants = TableDescriptor(...)` → таблица `auth_admin_grants`.
5. Alembic-миграция: enum + таблица + индекс.

## Этап 2 — Bootstrap

1. `App.bootstrap_owner(login, password)` в `service.py` — идемпотентно:
   - client_app `auth-admin` (key — константа) — создать, если нет;
   - если активный OWNER grant уже есть → no-op с сообщением;
   - иначе identity + PASSWORD credential (Argon2) + grant `OWNER` (`granted_by=NULL`).
2. `settings/auth.py`: `owner_login` / `owner_password` (`AUTH__OWNER_LOGIN/PASSWORD`);
   в LOCAL — дефолт `admin/admin`, вне LOCAL пароль обязателен для команды.
3. `manage.py bootstrap-owner` — тонкая CLI-обёртка; добавить в `make init`.
4. Проверка при старте web: нет активного OWNER →
   `log.error("Auth service is not initialized: run 'python manage.py bootstrap-owner'")`.
5. `data/init_data.sql`: убрать admin-сид (его заменяет bootstrap), оставить только `test-app`.

## Этап 3 — Login-флоу и JWT

1. Рефакторинг: выделить из `login_by_password` приватный
   `_verify_password_credential(identifier, password) -> Credential`
   (поиск, lockout, счётчики попыток) — чтобы не дублировать логику.
2. `App.login_by_admin(identifier, password, ip, ua)`:
   - `log_login_attempt(method="admin_password")`;
   - `_verify_password_credential`;
   - проверка активного grant; **нет grant → тот же `Invalid credentials`**
     (не раскрываем существование учётки);
   - сессия через `create_session` с client_app `auth-admin`.
3. `build_jwt_payload` начинает использовать свой параметр `client_app_id`: если это `auth-admin` —
   загрузить активный grant и добавить `role` (+ `aud: "auth-admin"`).
   Следствия конструкции:
   - refresh автоматически переиздаёт роль;
   - если grant отозван — `refresh_session` ревокает сессию и отказывает;
   - обычный `/auth/login/password` для той же учётки продолжит работать,
     но выдаст токен без роли — безопасно.

## Этап 4 — Guard и компонент

1. `web/auth.py`: `AdminClient(Client)` с обязательным `role: AdminRole`;
   `admin_jwt = JWT(payload_model=AdminClient, ...)` — все будущие `/admin/*` вешают
   `auth = admin_jwt`.
   - ⚠️ Проверить, как adc_webkit реагирует на отсутствие поля в payload
     (ожидается 401; если валидация мягкая — дублируем проверку в компоненте).
2. `services/components/current_admin.py`: REQUEST-scoped `CurrentAdmin` по образцу
   `CurrentIdentity`: identity `ACTIVE` **и** активный grant в БД (отзыв прав действует сразу,
   не дожидаясь истечения токена). Возвращает identity + role — OWNER-only операции
   (выдача грантов) позже проверяют role здесь.

## Этап 5 — Эндпоинты

| Route | Endpoint | Примечание |
|---|---|---|
| `POST /admin/auth/login` | `AdminLogin` | body `{login, password}` — без `client_app_id`, он системный |
| `POST /admin/auth/refresh` | `AdminRefreshSession` | тонкая обёртка над `refresh_session`: UI не должен знать UUID системного app |
| `GET /admin/auth/me` | `AdminMe` | `auth = admin_jwt`; identity_id + role — нужно будущему UI |

Новый файл `web/endpoints/admin_auth.py`, схемы в `schemas.py`, регистрация в `web/app.py`
и `web/endpoints/__init__.py`. Logout — реюз существующего `/auth/session/logout`.
CRUD над приложениями/провайдерами — вне скоупа, но guard-каркас будет готов.

## Этап 6 — Тесты и документация

- Тесты:
  - идемпотентность bootstrap;
  - admin-login: успех / неверный пароль с lockout / учётка без grant;
  - юзерский токен на админ-эндпоинте → 401/403;
  - refresh с отозванным grant → сессия ревокается;
  - `GET /admin/auth/me`.
- Доки: обновить CLAUDE.md (таблица auth-методов, структура), отметить пункт в `docs/roadmap.md`.
- В `docs/tech_debt.md` добавить замеченное попутно: `client_app.access_token_ttl_sec`
  не используется — access TTL всегда глобальный `cfg.auth.access_token_lifetime` (1 мин);
  для админки не блокер, но чинить стоит.

## Порядок и риски

Этапы строго последовательны: 1 → 2 → 3 → 4 → 5 → 6.

Точки неопределённости (проверяются по месту, на план не влияют):

- поведение `adc_webkit.JWT` с кастомной payload-моделью (этап 4);
- синтаксис partial unique index в Alembic (этап 1).
