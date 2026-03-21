"""Add ip_address and location to device_sessions (already created in initial migration)

Revision ID: e93fe883f0dd
Revises: 0001_create_all_tables
Create Date: 2026-03-08 20:11:44.415626

NOTE: Колонки ip_address и location уже созданы в миграции 0001_create_all_tables.
      Эта миграция оставлена как пустая заглушка для совместимости истории Alembic.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e93fe883f0dd'
down_revision: Union[str, None] = '0001_create_all_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Колонки уже созданы в 0001_create_all_tables — ничего делать не нужно.
    pass


def downgrade() -> None:
    pass