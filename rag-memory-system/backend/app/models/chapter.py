from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
import uuid

from app.database import Base


class StoryChapter(Base):
    __tablename__ = "story_chapters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_number = Column(Integer, nullable=False)
    chapter_marker = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
