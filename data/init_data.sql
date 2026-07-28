-- Тестовые данные: client_app для пользовательских флоу.
-- Админ создаётся отдельно: python manage.py bootstrap-owner
INSERT INTO auth.auth_client_apps (
    key,
    name,
    type,
    allowed_redirect_uris,
    allowed_scopes,
    access_token_ttl_sec,
    refresh_token_ttl_sec
)
SELECT
    'test-app',
    'Test Application',
    'PUBLIC',
    ARRAY []::text [],
    ARRAY []::text [],
    900,
    2592000
WHERE NOT EXISTS (
    SELECT 1
    FROM auth.auth_client_apps
    WHERE key = 'test-app'
);
