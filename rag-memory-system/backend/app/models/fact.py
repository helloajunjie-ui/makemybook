from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Index
import uuid

from app.database import Base


class MemoryFact(Base):
    __tablename__ = "memory_facts"

    __table_args__ = (
        Index("idx_memory_facts_book_chapter", "book_id", "chapter_marker"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String(36), ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_marker = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    # 💡 单机化改造：pgvector.Vector → Text(JSON)
    # 存入时 json.dumps(vector)，读取时 json.loads(embedding)
    # 余弦相似度在 Python 内存中用 numpy 计算
    embedding = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)  # 0=已压缩(非活跃), 1=活跃
    created_at = Column(DateTime(timezone=True), server_default=func.now())
