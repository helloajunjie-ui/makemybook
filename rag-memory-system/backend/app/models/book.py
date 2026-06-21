from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False, index=True)
    summary = Column(Text, default="")
    # 💡 书籍专属文风约束（领域数据，持久化到 PostgreSQL）
    custom_prompt = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
