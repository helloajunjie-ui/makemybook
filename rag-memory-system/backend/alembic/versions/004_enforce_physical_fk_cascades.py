"""enforce physical FK ON DELETE CASCADE for 3 tables

ORM 模型已定义 ForeignKey(..., ondelete='CASCADE')，但数据库实际缺失物理外键。
此迁移补全 story_chapters、story_chat_messages、story_outline_nodes 的外键约束。

Revision ID: 004
Revises: 003
Create Date: 2026-06-22 08:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. StoryChapter.book_id → books.id CASCADE
    op.create_foreign_key(
        'fk_chapter_book', 'story_chapters', 'books',
        ['book_id'], ['id'], ondelete='CASCADE'
    )
    # 2. StoryChatMessage.book_id → books.id CASCADE
    op.create_foreign_key(
        'fk_chat_book', 'story_chat_messages', 'books',
        ['book_id'], ['id'], ondelete='CASCADE'
    )
    # 3. StoryOutlineNode.pitch_id → story_pitches.id CASCADE
    op.create_foreign_key(
        'fk_outline_pitch', 'story_outline_nodes', 'story_pitches',
        ['pitch_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_chapter_book', 'story_chapters', type_='foreignkey')
    op.drop_constraint('fk_chat_book', 'story_chat_messages', type_='foreignkey')
    op.drop_constraint('fk_outline_pitch', 'story_outline_nodes', type_='foreignkey')
