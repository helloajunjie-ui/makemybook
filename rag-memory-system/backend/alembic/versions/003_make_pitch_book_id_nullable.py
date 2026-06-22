"""make story_pitches.book_id nullable=True for pitch-before-book flow

Revision ID: 003
Revises: 002
Create Date: 2026-06-22 05:51:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 💡 裂变推演时 pitch 先于 book 创建，book_id 必须允许为空
    op.alter_column('story_pitches', 'book_id',
                    existing_type=sa.Uuid(),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    op.alter_column('story_pitches', 'book_id',
                    existing_type=sa.Uuid(),
                    nullable=False,
                    existing_nullable=True)
