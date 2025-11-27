-- Скрипт для добавления тестовых данных: client_app и admin пользователя
-- Создаём тестовый client_app (если его ещё нет)
INSERT INTO auth.auth_client_apps (
        key,
        name,
        type,
        allowed_redirect_uris,
        allowed_scopes,
        access_token_ttl_sec,
        refresh_token_ttl_sec
    )
VALUES (
        'test-app',
        'Test Application',
        'PUBLIC',
        ARRAY []::text [],
        ARRAY []::text [],
        900,
        2592000
    ) ON CONFLICT (key) DO NOTHING;
-- Создаём admin пользователя (если его ещё нет)
DO $$
DECLARE v_identity_id UUID;
v_credential_exists BOOLEAN;
BEGIN -- Проверяем, существует ли уже admin credential
SELECT EXISTS(
        SELECT 1
        FROM auth.auth_credentials
        WHERE identifier = 'admin'
            AND type = 'PASSWORD'
            AND archived = false
    ) INTO v_credential_exists;
-- Если admin credential не существует, создаём identity и credential
IF NOT v_credential_exists THEN -- Создаём identity
INSERT INTO auth.auth_identities (tenant_id, status)
VALUES (NULL, 'ACTIVE')
RETURNING id INTO v_identity_id;
-- Создаём credential с паролем admin
INSERT INTO auth.auth_credentials (
        identity_id,
        type,
        identifier,
        secret_hash,
        failed_attempts
    )
VALUES (
        v_identity_id,
        'PASSWORD',
        'admin',
        '$argon2id$v=19$m=65536,t=3,p=4$IYRw7t17r7W2NuacEyIEgA$4xRCN/RFjTyrj/vYcA8jVSrFa7o0rhAIpp6sd1nkB+M',
        -- admin
        0
    );
END IF;
END $$;