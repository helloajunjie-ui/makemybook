from sqlalchemy import Column, String, Text, DateTime, func
import uuid

from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(100), nullable=False, index=True)
    summary = Column(Text, default="")
    custom_prompt = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
