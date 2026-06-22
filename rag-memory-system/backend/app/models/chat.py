from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
import uuid

from app.database import Base


class StoryChatMessage(Base):
    __tablename__ = "story_chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    type = Column(String(30), nullable=False)
    volume = Column(Integer, nullable=True)
    chapter = Column(Integer, nullable=True)
    title = Column(String(255), nullable=True)
    desc = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
