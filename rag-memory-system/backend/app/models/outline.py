from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class StoryOutlineNode(Base):
    __tablename__ = "story_outline_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pitch_id = Column(UUID(as_uuid=True), ForeignKey("story_pitches.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    core_goal = Column(Text, nullable=True)
    emotion_curve = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    estimated_chapters = Column(Integer, default=5)
    status = Column(String(50), default="pending")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
