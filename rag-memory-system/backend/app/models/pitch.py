from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class StoryPitch(Base):
    __tablename__ = "story_pitches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seed_text = Column(Text, nullable=False)
    variant_of = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    tone = Column(String(100), nullable=True)
    is_selected = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
