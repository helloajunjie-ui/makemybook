from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class StoryChatMessage(Base):
    __tablename__ = "story_chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    type = Column(String(30), nullable=False)
    volume = Column(Integer, nullable=True)
    chapter = Column(Integer, nullable=True)
    title = Column(String(255), nullable=True)
    desc = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
