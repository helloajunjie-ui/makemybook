from sqlalchemy import Column, Integer, String, Text, DateTime, func, Index, ForeignKey, UniqueConstraint
import uuid

from app.database import Base


class MemoryEntity(Base):
    __tablename__ = "memory_entities"

    __table_args__ = (
        UniqueConstraint("book_id", "entry_name", name="uix_book_entry"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    # 💡 单机化改造：ARRAY(String) → Text(JSON)
    # SQLite 不支持 ARRAY 类型，triggers 以 JSON 数组字符串存储
    triggers = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
