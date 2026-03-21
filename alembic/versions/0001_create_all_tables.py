"""Create all tables from scratch

Revision ID: 0001_create_all_tables
Revises:
Create Date: 2026-03-21

ЗАЧЕМ ЭТОТ ФАЙЛ:
  Исходная миграция e93fe883f0dd пыталась только добавить колонки в device_sessions,
  но сама таблица users (и все остальные) никогда не создавалась —
  отсюда ошибка: relation "users" does not exist.

ЧТО ДЕЛАТЬ:
  1. Удалить старую миграцию e93fe883f0dd_initial_tables.py
  2. Положить этот файл вместо неё
  3. Выполнить: docker exec akyl_backend alembic upgrade head
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_create_all_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',              sa.String(), primary_key=True, nullable=False),
        sa.Column('username',        sa.String(), nullable=False),
        sa.Column('is_bot',          sa.Boolean(), nullable=True, default=False),
        sa.Column('email',           sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('avatar_url',      sa.String(), nullable=True),
        sa.Column('name',            sa.String(), nullable=True),
        sa.Column('is_online',       sa.Boolean(), nullable=True, default=False),
        sa.Column('last_seen',       sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_users_id',         'users', ['id'],         unique=False)
    op.create_index('ix_users_username',   'users', ['username'],   unique=True)
    op.create_index('ix_users_name',       'users', ['name'],       unique=False)
    op.create_index('ix_users_is_bot',     'users', ['is_bot'],     unique=False)
    op.create_index('ix_users_is_online',  'users', ['is_online'],  unique=False)
    op.create_index('ix_users_created_at', 'users', ['created_at'], unique=False)

    # ── bot_configs ────────────────────────────────────────────────────────────
    op.create_table(
        'bot_configs',
        sa.Column('bot_id',      sa.String(), sa.ForeignKey('users.id'), primary_key=True, nullable=False),
        sa.Column('api_token',   sa.String(), nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('is_active',   sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',  sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_bot_configs_api_token',  'bot_configs', ['api_token'],  unique=True)
    op.create_index('ix_bot_configs_created_at', 'bot_configs', ['created_at'], unique=False)

    # ── device_sessions ────────────────────────────────────────────────────────
    op.create_table(
        'device_sessions',
        sa.Column('id',                 sa.String(), primary_key=True, nullable=False),
        sa.Column('user_id',            sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('refresh_token_hash', sa.String(), nullable=True),
        sa.Column('device_name',        sa.String(), nullable=True),
        sa.Column('push_token',         sa.String(), nullable=True),
        sa.Column('ip_address',         sa.String(), nullable=True),
        sa.Column('location',           sa.String(), nullable=True),
        sa.Column('is_active',          sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at',         sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',         sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_device_sessions_id',                  'device_sessions', ['id'],                 unique=False)
    op.create_index('ix_device_sessions_user_id',             'device_sessions', ['user_id'],            unique=False)
    op.create_index('ix_device_sessions_push_token',          'device_sessions', ['push_token'],         unique=False)
    op.create_index('ix_device_sessions_refresh_token_hash',  'device_sessions', ['refresh_token_hash'], unique=True)
    op.create_index('ix_device_sessions_created_at',          'device_sessions', ['created_at'],         unique=False)

    # ── chats ──────────────────────────────────────────────────────────────────
    op.create_table(
        'chats',
        sa.Column('id',         sa.String(), primary_key=True, nullable=False),
        sa.Column('type',       sa.String(), nullable=False),
        sa.Column('name',       sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_chats_id',         'chats', ['id'],         unique=False)
    op.create_index('ix_chats_type',       'chats', ['type'],       unique=False)
    op.create_index('ix_chats_updated_at', 'chats', ['updated_at'], unique=False)
    op.create_index('ix_chats_created_at', 'chats', ['created_at'], unique=False)

    # ── messages ───────────────────────────────────────────────────────────────
    op.create_table(
        'messages',
        sa.Column('id',         sa.String(), primary_key=True, nullable=False),
        sa.Column('chat_id',    sa.String(), sa.ForeignKey('chats.id'), nullable=False),
        sa.Column('sender_id',  sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('text',       sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_messages_id',         'messages', ['id'],         unique=False)
    op.create_index('ix_messages_chat_id',    'messages', ['chat_id'],    unique=False)
    op.create_index('ix_messages_sender_id',  'messages', ['sender_id'],  unique=False)
    op.create_index('ix_messages_created_at', 'messages', ['created_at'], unique=False)

    # ── chat_members ───────────────────────────────────────────────────────────
    op.create_table(
        'chat_members',
        sa.Column('id',            sa.String(), primary_key=True, nullable=False),
        sa.Column('chat_id',       sa.String(), sa.ForeignKey('chats.id'), nullable=False),
        sa.Column('user_id',       sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('last_read_msg', sa.String(),
                  sa.ForeignKey('messages.id', use_alter=True, name='fk_chat_members_last_read_msg'),
                  nullable=True),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',    sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_chat_members_id',         'chat_members', ['id'],         unique=False)
    op.create_index('ix_chat_members_chat_id',    'chat_members', ['chat_id'],    unique=False)
    op.create_index('ix_chat_members_user_id',    'chat_members', ['user_id'],    unique=False)
    op.create_index('ix_chat_members_created_at', 'chat_members', ['created_at'], unique=False)

    # ── attachments ────────────────────────────────────────────────────────────
    op.create_table(
        'attachments',
        sa.Column('id',         sa.String(), primary_key=True, nullable=False),
        sa.Column('message_id', sa.String(), sa.ForeignKey('messages.id'), nullable=False),
        sa.Column('file_url',   sa.String(), nullable=False),
        sa.Column('file_type',  sa.String(), nullable=False),
        sa.Column('file_size',  sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_attachments_id',         'attachments', ['id'],         unique=False)
    op.create_index('ix_attachments_message_id', 'attachments', ['message_id'], unique=False)
    op.create_index('ix_attachments_created_at', 'attachments', ['created_at'], unique=False)

    # ── contacts ───────────────────────────────────────────────────────────────
    op.create_table(
        'contacts',
        sa.Column('id',              sa.String(), primary_key=True, nullable=False),
        sa.Column('owner_id',        sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('contact_user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('saved_name',      sa.String(), nullable=False),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_contacts_id',              'contacts', ['id'],              unique=False)
    op.create_index('ix_contacts_owner_id',        'contacts', ['owner_id'],        unique=False)
    op.create_index('ix_contacts_contact_user_id', 'contacts', ['contact_user_id'], unique=False)
    op.create_index('ix_contacts_created_at',      'contacts', ['created_at'],      unique=False)

    # ── user_settings ──────────────────────────────────────────────────────────
    op.create_table(
        'user_settings',
        sa.Column('user_id',           sa.String(), sa.ForeignKey('users.id'), primary_key=True, nullable=False),
        sa.Column('push_enabled',      sa.Boolean(), nullable=True, default=True),
        sa.Column('theme_pref',        sa.String(),  nullable=True, default='system'),
        sa.Column('subscription_tier', sa.String(),  nullable=True, default='free'),
        sa.Column('referral_code',     sa.String(),  nullable=True),
        sa.Column('created_at',        sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',        sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_user_settings_referral_code', 'user_settings', ['referral_code'], unique=True)
    op.create_index('ix_user_settings_created_at',    'user_settings', ['created_at'],    unique=False)


def downgrade() -> None:
    # Удаляем в обратном порядке (зависимые таблицы первыми)
    op.drop_table('user_settings')
    op.drop_table('contacts')
    op.drop_table('attachments')
    op.drop_table('chat_members')
    op.drop_table('messages')
    op.drop_table('chats')
    op.drop_table('device_sessions')
    op.drop_table('bot_configs')
    op.drop_table('users')