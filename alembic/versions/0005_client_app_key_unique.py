"""unique key for client apps

Без уникальности key можно было создать второй 'auth-admin', а lookup
по key (limit=1, без ORDER BY) выбирал строку недетерминированно.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    # Дубликаты (если завелись до индекса) архивируем, оставляя самую старую строку
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
