from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class StoryApiConfig(Base):
    __tablename__ = "story_api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preset_name = Column(String(50), nullable=False, unique=True)
    api_key = Column(Text, nullable=False, default="")
    base_url = Column(String(500), nullable=False, default="")
    model = Column(String(100), nullable=False, default="")
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
