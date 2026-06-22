from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
import uuid

from app.database import Base


class StoryPitch(Base):
    __tablename__ = "story_pitches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=True, index=True)
    seed_text = Column(Text, nullable=False)
    variant_of = Column(String(36), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    tone = Column(String(100), nullable=True)
    details = Column(Text, nullable=True, default="")
    is_selected = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
