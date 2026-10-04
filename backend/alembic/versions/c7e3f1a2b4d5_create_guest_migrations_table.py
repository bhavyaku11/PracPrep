"""create_guest_migrations_table

Revision ID: c7e3f1a2b4d5
Revises: 560f2b7c6d76
Create Date: 2026-10-04 15:00:00.000000+00:00

Adds the guest_migrations table for tracking batch guest data migrations
and enforcing idempotency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e3f1a2b4d5'
down_revision: Union[str, None] = '560f2b7c6d76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guest_migrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'completed'")),
        sa.Column('experiments_migrated', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('viva_sessions_migrated', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('viva_answers_migrated', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_user_guest_migration_idempotency'),
    )
    op.create_index(op.f('ix_guest_migrations_user_id'), 'guest_migrations', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_guest_migrations_user_id'), table_name='guest_migrations')
    op.drop_table('guest_migrations')
