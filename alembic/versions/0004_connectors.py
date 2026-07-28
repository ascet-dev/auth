"""connectors: экземпляры способов входа + M2M на приложения

Поглощает auth_oauth_providers и auth_method_settings.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_connectors',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('type', postgresql.ENUM(name='auth_method', schema='auth', create_type=False), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    op.create_index(
        'uq_auth_connectors_key',
        'auth_connectors',
        ['key'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )

    op.create_table('auth_client_app_connectors',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('client_app_id', sa.Uuid(), nullable=False),
    sa.Column('connector_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['client_app_id'], ['auth.auth_client_apps.id'], ),
    sa.ForeignKeyConstraint(['connector_id'], ['auth.auth_connectors.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    op.create_index(
        'uq_auth_client_app_connectors_pair',
        'auth_client_app_connectors',
        ['client_app_id', 'connector_id'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )

    # --- data: OAuth-провайдеры становятся коннекторами type=OAUTH
    op.execute("""
        INSERT INTO auth.auth_connectors (key, type, name, enabled, settings, archived)
        SELECT
            name,
            'OAUTH'::auth.auth_method,
            name,
            enabled,
            jsonb_strip_nulls(jsonb_build_object(
                'client_id', client_id,
                'client_secret', client_secret,
                'auth_url', auth_url,
                'token_url', token_url,
                'jwks_url', jwks_url,
                'userinfo_url', userinfo_url
            )),
            archived
        FROM auth.auth_oauth_providers
    """)

    # --- data: настройки TMA/PASSWORD из auth_method_settings → коннекторы
    op.execute("""
        INSERT INTO auth.auth_connectors (key, type, name, enabled, settings)
        SELECT 'tma', 'TMA'::auth.auth_method, 'Telegram Mini App', enabled, coalesce(settings, '{}'::jsonb)
        FROM auth.auth_method_settings
        WHERE method = 'TMA' AND archived = false AND settings IS NOT NULL AND settings != '{}'::jsonb
    """)
    op.execute("""
        INSERT INTO auth.auth_connectors (key, type, name, enabled, settings)
        SELECT 'password', 'PASSWORD'::auth.auth_method, 'Password', enabled, coalesce(settings, '{}'::jsonb)
        FROM auth.auth_method_settings
        WHERE method = 'PASSWORD' AND archived = false
          AND (enabled = false OR (settings IS NOT NULL AND settings != '{}'::jsonb))
    """)

    op.drop_table('auth_oauth_providers', schema='auth')
    op.drop_index('uq_auth_method_settings_method', table_name='auth_method_settings', schema='auth')
    op.drop_table('auth_method_settings', schema='auth')
    op.drop_column('auth_client_apps', 'allowed_auth_methods', schema='auth')


def downgrade():
    # Обратной миграции данных нет: коннекторы — надмножество старых таблиц
    op.add_column(
        'auth_client_apps',
        sa.Column('allowed_auth_methods', postgresql.ARRAY(sa.String()), nullable=True),
        schema='auth',
    )
    op.create_table('auth_method_settings',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('method', postgresql.ENUM(name='auth_method', schema='auth', create_type=False), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    op.create_index(
        'uq_auth_method_settings_method', 'auth_method_settings', ['method'],
        unique=True, schema='auth', postgresql_where=sa.text('archived = false'),
    )
    op.create_table('auth_oauth_providers',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('client_id', sa.String(), nullable=False),
    sa.Column('client_secret', sa.String(), nullable=False),
    sa.Column('auth_url', sa.String(), nullable=False),
    sa.Column('token_url', sa.String(), nullable=False),
    sa.Column('jwks_url', sa.String(), nullable=True),
    sa.Column('userinfo_url', sa.String(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    op.drop_index('uq_auth_client_app_connectors_pair', table_name='auth_client_app_connectors', schema='auth')
    op.drop_table('auth_client_app_connectors', schema='auth')
    op.drop_index('uq_auth_connectors_key', table_name='auth_connectors', schema='auth')
    op.drop_table('auth_connectors', schema='auth')
