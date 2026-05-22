"""create tables

Revision ID: 0001_create_tables
Revises: 
Create Date: 2026-05-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = '0001_create_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('updated_at', sa.String(length=32), nullable=False, server_default=''),
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'])
    op.create_index('ix_sessions_session_id', 'sessions', ['session_id'])

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(length=32), nullable=False, server_default=''),
    )
    op.create_index('ix_messages_id', 'messages', ['id'])
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trace_id', sa.String(length=64), nullable=False),
        sa.Column('event', sa.String(length=64), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(length=32), nullable=False, server_default=''),
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_trace_id', 'audit_logs', ['trace_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_trace_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_messages_session_id', table_name='messages')
    op.drop_index('ix_messages_id', table_name='messages')
    op.drop_table('messages')

    op.drop_index('ix_sessions_session_id', table_name='sessions')
    op.drop_index('ix_sessions_id', table_name='sessions')
    op.drop_table('sessions')
