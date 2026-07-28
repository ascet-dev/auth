# Tech debt

- [x] auth схема нужна миграции, но не создается — закрыто: `alembic/env.py` делает
      `CREATE SCHEMA IF NOT EXISTS` до старта миграций (иначе падало создание `auth.alembic_version`)
- [ ] `client_app.access_token_ttl_sec` не используется: access TTL всегда глобальный
      `cfg.auth.access_token_lifetime` (1 мин). Для админки не блокер, но чинить стоит
      (брать TTL из client_app в `build_jwt_payload`)
- [ ] refresh-токен админки хранится в localStorage (XSS-поверхность). Hardening: httpOnly-cookie
      + CSRF-защита — потребует новой backend-поверхности (set/read cookie в login/refresh)
- [ ] ошибки REQUEST-компонентов (`CurrentIdentity`) в пользовательских эндпоинтах маппятся в 500
      (generic handler), в админских — в 401 через `admin_scope`. Унифицировать (401 везде)
- [ ] `alembic downgrade` не дропает enum-типы из 0001 → `make db-reset` падает на
      `CREATE TYPE ... already exists` (в 0002 downgrade уже дропает `admin_role`)
- [ ] `settings/doc.py` (`cfg.doc`) не подключён к `Web.doc` — Swagger живёт с дефолтным тайтлом
- [ ] `ENV` читается и из процесса (`settings/env.py`), и через `cfg.env` — два источника истины,
      `.env` может их рассинхронизировать
