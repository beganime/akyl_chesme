"""add name and avatar_url to chats

Revision ID: a1b2c3d4e5f6
Revises: e93fe883f0dd
Create Date: 2026-03-23 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e93fe883f0dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем колонки name и avatar_url в таблицу chats
    op.add_column('chats', sa.Column('name', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('avatar_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('chats', 'avatar_url')
    op.drop_column('chats', 'name')