from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid

from app.database import Base
from app.config import settings


class MemoryFact(Base):
    __tablename__ = "memory_facts"

    __table_args__ = (
        Index("idx_memory_facts_book_chapter", "book_id", "chapter_marker"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_marker = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.embedding_dim), nullable=True)
    is_active = Column(Integer, default=1)  # 0=已压缩(非活跃), 1=活跃; 保留 Integer 避免 Alembic 迁移风险
    created_at = Column(DateTime(timezone=True), server_default=func.now())
