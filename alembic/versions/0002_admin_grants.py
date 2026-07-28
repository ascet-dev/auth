"""admin grants

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_admin_grants',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('updated', sa.DateTime(), server_default=sa.text("(now() at time zone 'utc')"), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('identity_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('OWNER', 'ADMIN', name='admin_role', schema='auth'), nullable=True),
    sa.Column('granted_by', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['identity_id'], ['auth.auth_identities.id'], ),
    sa.ForeignKeyConstraint(['granted_by'], ['auth.auth_identities.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='auth'
    )
    # Из-за soft delete обычный unique не подходит: после отзыва (archived=true)
    # грант должен быть выдаваем повторно.
    op.create_index(
        'uq_auth_admin_grants_identity_active',
        'auth_admin_grants',
        ['identity_id'],
        unique=True,
        schema='auth',
        postgresql_where=sa.text('archived = false'),
    )


def downgrade():
    op.drop_index('uq_auth_admin_grants_identity_active', table_name='auth_admin_grants', schema='auth')
    op.drop_table('auth_admin_grants', schema='auth')
    op.execute('DROP TYPE IF EXISTS auth.admin_role')
