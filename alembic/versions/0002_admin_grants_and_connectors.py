"""admin grants + connectors + unique client app key

Схлопнутая миграция: админские гранты, коннекторы (экземпляры способов входа)
с переливкой из auth_oauth_providers, уникальный key у client apps.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

TIMESTAMPS = (
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
)


def upgrade():
    # --- админские права ---------------------------------------------------
    op.create_table(
        'auth_admin_grants',
        *(c.copy() for c in TIMESTAMPS),
        sa.Column('identity_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('OWNER', 'ADMIN', name='admin_role', schema='auth'), nullable=True),
        sa.Column('granted_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['identity_id'], ['auth.auth_identities.id'], ),
        sa.ForeignKeyConstraint(['granted_by'], ['auth.auth_identities.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    # Soft delete: обычный unique не подходит, иначе после отзыва грант
    # нельзя выдать повторно
    op.create_index(
        'uq_auth_admin_grants_identity_active',
        'auth_admin_grants',
        ['identity_id'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )

    # --- коннекторы (экземпляры способов входа) ----------------------------
    op.create_table(
        'auth_connectors',
        *(c.copy() for c in TIMESTAMPS),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column(
            'type',
            sa.Enum('PASSWORD', 'OTP', 'TMA', 'OAUTH', name='auth_method', schema='auth'),
            nullable=True,
        ),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    op.create_index(
        'uq_auth_connectors_key',
        'auth_connectors',
        ['key'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )

    op.create_table(
        'auth_client_app_connectors',
        *(c.copy() for c in TIMESTAMPS),
        sa.Column('client_app_id', sa.Uuid(), nullable=False),
        sa.Column('connector_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['client_app_id'], ['auth.auth_client_apps.id'], ),
        sa.ForeignKeyConstraint(['connector_id'], ['auth.auth_connectors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    op.create_index(
        'uq_auth_client_app_connectors_pair',
        'auth_client_app_connectors',
        ['client_app_id', 'connector_id'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )

    # Существующие OAuth-провайдеры становятся коннекторами type=OAUTH
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
    op.drop_table('auth_oauth_providers', schema='auth')

    # --- уникальность key у client apps ------------------------------------
    # Без неё можно было создать второй 'auth-admin', а lookup по key
    # (limit=1, без ORDER BY) выбирал строку недетерминированно
    op.execute("""
        UPDATE auth.auth_client_apps AS a
        SET archived = true
        WHERE archived = false
          AND EXISTS (
              SELECT 1 FROM auth.auth_client_apps AS b
              WHERE b.key = a.key AND b.archived = false
                AND (b.created, b.id) < (a.created, a.id)
          )
    """)
    op.create_index(
        'uq_auth_client_apps_key',
        'auth_client_apps',
        ['key'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )


def downgrade():
    op.drop_index('uq_auth_client_apps_key', table_name='auth_client_apps', schema='auth')

    op.create_table(
        'auth_oauth_providers',
        *(c.copy() for c in TIMESTAMPS),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('client_secret', sa.String(), nullable=False),
        sa.Column('auth_url', sa.String(), nullable=False),
        sa.Column('token_url', sa.String(), nullable=False),
        sa.Column('jwks_url', sa.String(), nullable=True),
        sa.Column('userinfo_url', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    op.execute("""
        INSERT INTO auth.auth_oauth_providers (
            name, client_id, client_secret, auth_url, token_url, jwks_url, userinfo_url, enabled, archived
        )
        SELECT
            key,
            coalesce(settings->>'client_id', ''),
            coalesce(settings->>'client_secret', ''),
            coalesce(settings->>'auth_url', ''),
            coalesce(settings->>'token_url', ''),
            settings->>'jwks_url',
            settings->>'userinfo_url',
            enabled,
            archived
        FROM auth.auth_connectors
        WHERE type = 'OAUTH'
    """)

    op.drop_index('uq_auth_client_app_connectors_pair', table_name='auth_client_app_connectors', schema='auth')
    op.drop_table('auth_client_app_connectors', schema='auth')
    op.drop_index('uq_auth_connectors_key', table_name='auth_connectors', schema='auth')
    op.drop_table('auth_connectors', schema='auth')
    op.execute('DROP TYPE IF EXISTS auth.auth_method')

    op.drop_index('uq_auth_admin_grants_identity_active', table_name='auth_admin_grants', schema='auth')
    op.drop_table('auth_admin_grants', schema='auth')
    op.execute('DROP TYPE IF EXISTS auth.admin_role')
