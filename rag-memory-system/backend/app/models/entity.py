from sqlalchemy import Column, Integer, String, ARRAY, DateTime, func, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class MemoryEntity(Base):
    __tablename__ = "memory_entities"

    __table_args__ = (
        UniqueConstraint("book_id", "entry_name", name="uix_book_entry"),
        Index("idx_entity_triggers_gin", "triggers", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    triggers = Column(ARRAY(String), nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
