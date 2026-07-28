"""auth method settings + client_app.allowed_auth_methods

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_method_settings',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('method', sa.Enum('PASSWORD', 'OTP', 'TMA', 'OAUTH', name='auth_method', schema='auth'), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    op.create_index(
        'uq_auth_method_settings_method',
        'auth_method_settings',
        ['method'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )
    # Whitelist способов входа на приложение; NULL = все включённые глобально
    op.add_column(
        'auth_client_apps',
        sa.Column('allowed_auth_methods', postgresql.ARRAY(sa.String()), nullable=True),
        schema='auth',
    )


def downgrade():
    op.drop_column('auth_client_apps', 'allowed_auth_methods', schema='auth')
    op.drop_index('uq_auth_method_settings_method', table_name='auth_method_settings', schema='auth')
    op.drop_table('auth_method_settings', schema='auth')
    op.execute('DROP TYPE IF EXISTS auth.auth_method')
