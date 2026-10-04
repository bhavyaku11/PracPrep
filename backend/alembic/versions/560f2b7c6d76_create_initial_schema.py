"""create_initial_schema

Revision ID: 560f2b7c6d76
Revises: 
Create Date: 2026-10-04 07:47:51.423503+00:00

Baseline migration creating the 7 core domain tables for PracPrep:
- users
- user_settings
- experiments
- preparation_checklists
- viva_sessions
- viva_answers
- uploaded_documents
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '560f2b7c6d76'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('university', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('auth_provider', sa.String(length=50), nullable=False, server_default=sa.text("'local'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. user_settings table
    op.create_table(
        'user_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('default_difficulty', sa.String(length=20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('default_question_count', sa.Integer(), nullable=False, server_default=sa.text('5')),
        sa.Column('preferred_focus', sa.String(length=50), nullable=False, server_default=sa.text("'all'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_settings_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_settings')),
        sa.UniqueConstraint('user_id', name=op.f('uq_user_settings_user_id'))
    )
    op.create_index(op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True)

    # 3. experiments table
    op.create_table(
        'experiments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('experiment_number', sa.String(length=50), nullable=True),
        sa.Column('course_semester', sa.String(length=50), nullable=True),
        sa.Column('creation_method', sa.String(length=50), nullable=False, server_default=sa.text("'manual'")),
        sa.Column('has_manual_file', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'ready'")),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('objective', sa.Text(), nullable=True),
        sa.Column('theory', sa.Text(), nullable=True),
        sa.Column('apparatus', sa.Text(), nullable=True),
        sa.Column('procedure', sa.Text(), nullable=True),
        sa.Column('observations', sa.Text(), nullable=True),
        sa.Column('calculations', sa.Text(), nullable=True),
        sa.Column('precautions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_experiments_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_experiments'))
    )
    op.create_index(op.f('ix_experiments_id'), 'experiments', ['id'], unique=False)
    op.create_index(op.f('ix_experiments_user_id'), 'experiments', ['user_id'], unique=False)
    op.create_index(op.f('ix_experiments_subject'), 'experiments', ['subject'], unique=False)
    op.create_index(op.f('ix_experiments_status'), 'experiments', ['status'], unique=False)

    # 4. preparation_checklists table
    op.create_table(
        'preparation_checklists',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.UUID(), nullable=False),
        sa.Column('items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], name=op.f('fk_preparation_checklists_experiment_id_experiments'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_preparation_checklists')),
        sa.UniqueConstraint('experiment_id', name=op.f('uq_preparation_checklists_experiment_id'))
    )
    op.create_index(op.f('ix_preparation_checklists_experiment_id'), 'preparation_checklists', ['experiment_id'], unique=True)

    # 5. viva_sessions table
    op.create_table(
        'viva_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.UUID(), nullable=False),
        sa.Column('difficulty', sa.String(length=50), nullable=False, server_default=sa.text("'intermediate'")),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default=sa.text('5')),
        sa.Column('topic_focus', sa.String(length=50), nullable=False, server_default=sa.text("'mixed'")),
        sa.Column('provider_mode', sa.String(length=50), nullable=False, server_default=sa.text("'demonstration'")),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_score', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default=sa.text('5')),
        sa.Column('questions_answered', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('partially_correct_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('incorrect_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('topic_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('weak_topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('strong_topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('revision_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], name=op.f('fk_viva_sessions_experiment_id_experiments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_viva_sessions_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_viva_sessions'))
    )
    op.create_index(op.f('ix_viva_sessions_id'), 'viva_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_viva_sessions_user_id'), 'viva_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_viva_sessions_experiment_id'), 'viva_sessions', ['experiment_id'], unique=False)

    # 6. viva_answers table
    op.create_table(
        'viva_answers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.String(length=100), nullable=True),
        sa.Column('question_number', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('topic', sa.String(length=50), nullable=False, server_default=sa.text("'theory'")),
        sa.Column('difficulty', sa.String(length=50), nullable=False, server_default=sa.text("'intermediate'")),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('student_answer', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('verdict', sa.String(length=50), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('expected_answer', sa.Text(), nullable=True),
        sa.Column('what_you_got_right', sa.Text(), nullable=True),
        sa.Column('what_was_missing', sa.Text(), nullable=True),
        sa.Column('suggested_improvement', sa.Text(), nullable=True),
        sa.Column('key_points_covered', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('key_points_missed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evaluation_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['viva_sessions.id'], name=op.f('fk_viva_answers_session_id_viva_sessions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_viva_answers'))
    )
    op.create_index(op.f('ix_viva_answers_session_id'), 'viva_answers', ['session_id'], unique=False)

    # 7. uploaded_documents table
    op.create_table(
        'uploaded_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.UUID(), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], name=op.f('fk_uploaded_documents_experiment_id_experiments'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_uploaded_documents_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_uploaded_documents'))
    )
    op.create_index(op.f('ix_uploaded_documents_id'), 'uploaded_documents', ['id'], unique=False)
    op.create_index(op.f('ix_uploaded_documents_user_id'), 'uploaded_documents', ['user_id'], unique=False)
    op.create_index(op.f('ix_uploaded_documents_experiment_id'), 'uploaded_documents', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_uploaded_documents_status'), 'uploaded_documents', ['status'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_index(op.f('ix_uploaded_documents_status'), table_name='uploaded_documents')
    op.drop_index(op.f('ix_uploaded_documents_experiment_id'), table_name='uploaded_documents')
    op.drop_index(op.f('ix_uploaded_documents_user_id'), table_name='uploaded_documents')
    op.drop_index(op.f('ix_uploaded_documents_id'), table_name='uploaded_documents')
    op.drop_table('uploaded_documents')

    op.drop_index(op.f('ix_viva_answers_session_id'), table_name='viva_answers')
    op.drop_table('viva_answers')

    op.drop_index(op.f('ix_viva_sessions_experiment_id'), table_name='viva_sessions')
    op.drop_index(op.f('ix_viva_sessions_user_id'), table_name='viva_sessions')
    op.drop_index(op.f('ix_viva_sessions_id'), table_name='viva_sessions')
    op.drop_table('viva_sessions')

    op.drop_index(op.f('ix_preparation_checklists_experiment_id'), table_name='preparation_checklists')
    op.drop_table('preparation_checklists')

    op.drop_index(op.f('ix_experiments_status'), table_name='experiments')
    op.drop_index(op.f('ix_experiments_subject'), table_name='experiments')
    op.drop_index(op.f('ix_experiments_user_id'), table_name='experiments')
    op.drop_index(op.f('ix_experiments_id'), table_name='experiments')
    op.drop_table('experiments')

    op.drop_index(op.f('ix_user_settings_user_id'), table_name='user_settings')
    op.drop_table('user_settings')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
