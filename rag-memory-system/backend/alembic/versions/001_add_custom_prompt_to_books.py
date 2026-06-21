"""add custom_prompt column to books table

Revision ID: 001
Revises:
Create Date: 2026-06-22 05:09:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('books', sa.Column('custom_prompt', sa.Text(), nullable=True, server_default=''))


def downgrade() -> None:
    op.drop_column('books', 'custom_prompt')
