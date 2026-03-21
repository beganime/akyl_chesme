"""Create all tables from scratch

Revision ID: 0001_create_all_tables
Revises: 
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_create_all_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',              sa.String(),  primary_key=True,  nullable=False),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('username',        sa.String(),  unique=True,  nullable=False),
        sa.Column('is_bot',          sa.Boolean(), default=False, nullable=True),
        sa.Column('email',           sa.String(),  nullable=True),
        sa.Column('hashed_password', sa.String(),  nullable=True),
        sa.Column('avatar_url',      sa.String(),  nullable=True),
        sa.Column('name',            sa.String(),  nullable=True),
        sa.Column('is_online',       sa.Boolean(), default=False, nullable=True),
        sa.Column('last_seen',       sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_id',       'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_name',     'users', ['name'])
    op.create_index('ix_users_is_bot',   'users', ['is_bot'])
    op.create_index('ix_users_is_online','users', ['is_online'])
    op.create_index('ix_users_created_at','users', ['created_at'])

    # ── bot_configs ──────────────────────────────────────────────
    op.create_table(
        'bot_configs',
        sa.Column('bot_id',      sa.String(), sa.ForeignKey('users.id'), primary_key=True, nullable=False),
        sa.Column('created_at',  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('api_token',   sa.String(), unique=True, nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('is_active',   sa.Boolean(), default=True, nullable=True),
    )
    op.create_index('ix_bot_configs_api_token', 'bot_configs', ['api_token'], unique=True)

    # ── device_sessions ──────────────────────────────────────────
    op.create_table(
        'device_sessions',
        sa.Column('id',                  sa.String(), primary_key=True, nullable=False),
        sa.Column('created_at',          sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',          sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('user_id',             sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('refresh_token_hash',  sa.String(), unique=True, nullable=True),
        sa.Column('device_name',         sa.String(), nullable=True),
        sa.Column('push_token',          sa.String(), nullable=True),
        sa.Column('ip_address',          sa.String(), nullable=True),
        sa.Column('location',            sa.String(), nullable=True),
        sa.Column('is_active',           sa.Boolean(), default=True, nullable=True),
    )
    op.create_index('ix_device_sessions_id',         'device_sessions', ['id'])
    op.create_index('ix_device_sessions_user_id',    'device_sessions', ['user_id'])
    op.create_index('ix_device_sessions_push_token', 'device_sessions', ['push_token'])
    op.create_index('ix_device_sessions_created_at', 'device_sessions', ['created_at'])

    # ── chats ────────────────────────────────────────────────────
    op.create_table(
        'chats',
        sa.Column('id',         sa.String(), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True, index=True),
        sa.Column('type',       sa.String(), nullable=False),   # dialog / group / channel / bot
        sa.Column('name',       sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
    )
    op.create_index('ix_chats_id',         'chats', ['id'])
    op.create_index('ix_chats_type',       'chats', ['type'])
    op.create_index('ix_chats_updated_at', 'chats', ['updated_at'])
    op.create_index('ix_chats_created_at', 'chats', ['created_at'])

    # ── messages (нужна раньше chat_members из-за FK last_read_msg) ──
    op.create_table(
        'messages',
        sa.Column('id',         sa.String(), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('chat_id',    sa.String(), sa.ForeignKey('chats.id'),  nullable=False),
        sa.Column('sender_id',  sa.String(), sa.ForeignKey('users.id'),  nullable=False),
        sa.Column('text',       sa.Text(),   nullable=True),
    )
    op.create_index('ix_messages_id',         'messages', ['id'])
    op.create_index('ix_messages_chat_id',    'messages', ['chat_id'])
    op.create_index('ix_messages_sender_id',  'messages', ['sender_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])

    # ── chat_members ─────────────────────────────────────────────
    op.create_table(
        'chat_members',
        sa.Column('id',           sa.String(), primary_key=True, nullable=False),
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('chat_id',      sa.String(), sa.ForeignKey('chats.id'),    nullable=False),
        sa.Column('user_id',      sa.String(), sa.ForeignKey('users.id'),    nullable=False),
        sa.Column('last_read_msg',sa.String(), sa.ForeignKey('messages.id', use_alter=True, name='fk_chat_members_last_read_msg'), nullable=True),
    )
    op.create_index('ix_chat_members_id',      'chat_members', ['id'])
    op.create_index('ix_chat_members_chat_id', 'chat_members', ['chat_id'])
    op.create_index('ix_chat_members_user_id', 'chat_members', ['user_id'])
    op.create_index('ix_chat_members_created_at', 'chat_members', ['created_at'])

    # ── attachments ──────────────────────────────────────────────
    op.create_table(
        'attachments',
        sa.Column('id',         sa.String(),  primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('message_id', sa.String(), sa.ForeignKey('messages.id'), nullable=False),
        sa.Column('file_url',   sa.String(), nullable=False),
        sa.Column('file_type',  sa.String(), nullable=False),
        sa.Column('file_size',  sa.Integer(), nullable=True),
    )
    op.create_index('ix_attachments_id',         'attachments', ['id'])
    op.create_index('ix_attachments_message_id', 'attachments', ['message_id'])
    op.create_index('ix_attachments_created_at', 'attachments', ['created_at'])

    # ── contacts ─────────────────────────────────────────────────
    op.create_table(
        'contacts',
        sa.Column('id',              sa.String(), primary_key=True, nullable=False),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('owner_id',        sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('contact_user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('saved_name',      sa.String(), nullable=False),
    )
    op.create_index('ix_contacts_id',              'contacts', ['id'])
    op.create_index('ix_contacts_owner_id',        'contacts', ['owner_id'])
    op.create_index('ix_contacts_contact_user_id', 'contacts', ['contact_user_id'])
    op.create_index('ix_contacts_created_at',      'contacts', ['created_at'])

    # ── user_settings ────────────────────────────────────────────
    op.create_table(
        'user_settings',
        sa.Column('user_id',           sa.String(), sa.ForeignKey('users.id'), primary_key=True, nullable=False),
        sa.Column('created_at',        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at',        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('push_enabled',      sa.Boolean(), default=True, nullable=True),
        sa.Column('theme_pref',        sa.String(), default='system', nullable=True),
        sa.Column('subscription_tier', sa.String(), default='free', nullable=True),
        sa.Column('referral_code',     sa.String(), unique=True, nullable=True),
    )
    op.create_index('ix_user_settings_referral_code', 'user_settings', ['referral_code'], unique=True)


def downgrade() -> None:
    op.drop_table('user_settings')
    op.drop_table('contacts')
    op.drop_table('attachments')
    op.drop_table('chat_members')
    op.drop_table('messages')
    op.drop_table('chats')
    op.drop_table('device_sessions')
    op.drop_table('bot_configs')
    op.drop_table('users')