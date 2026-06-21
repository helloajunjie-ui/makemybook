"""add foreign key cascades for referential integrity

Revision ID: 002
Revises: 001
Create Date: 2026-06-22 05:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
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
    # 4. StoryPitch.book_id → books.id CASCADE
    op.add_column('story_pitches', sa.Column('book_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_pitch_book', 'story_pitches', 'books',
        ['book_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_pitch_book_id', 'story_pitches', ['book_id'])


def downgrade() -> None:
    op.drop_constraint('fk_chapter_book', 'story_chapters', type_='foreignkey')
    op.drop_constraint('fk_chat_book', 'story_chat_messages', type_='foreignkey')
    op.drop_constraint('fk_outline_pitch', 'story_outline_nodes', type_='foreignkey')
    op.drop_constraint('fk_pitch_book', 'story_pitches', type_='foreignkey')
    op.drop_index('ix_pitch_book_id', 'story_pitches')
    op.drop_column('story_pitches', 'book_id')
