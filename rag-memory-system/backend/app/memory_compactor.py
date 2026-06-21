import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database import async_engine
from app.models.entity import MemoryEntity
from app.models.fact import MemoryFact
from app.llm_client import compact_old_facts

AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

COMPACTION_THRESHOLD = 10


async def run_compaction_task(entity_id: str, current_chapter: int):
    """
    后台静默执行的记忆快照与压缩任务
    """
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(MemoryEntity, MemoryFact).join(
                MemoryFact, MemoryEntity.id == MemoryFact.entity_id
            ).where(
                MemoryEntity.id == entity_id,
                MemoryFact.is_active == True
            ).order_by(MemoryFact.chapter_marker.asc())

            result = await db.execute(stmt)
            rows = result.all()

            if len(rows) <= COMPACTION_THRESHOLD:
                return

            print(f"[Memory GC] 实体 {entity_id} 活跃事实达到 {len(rows)} 条，触发炼化机制...")

            entity = rows[0][0]
            facts = [r[1] for r in rows]
            facts_texts = [f.content for f in facts]

            compacted_texts = await compact_old_facts(entity.entry_name, entity.type, facts_texts)
            if not compacted_texts:
                return

            for fact in facts:
                fact.is_active = False

            for text in compacted_texts:
                new_fact = MemoryFact(
                    entity_id=entity.id,
                    chapter_marker=current_chapter,
                    content=text,
                    is_active=True,
                )
                db.add(new_fact)

            await db.commit()
            print(f"[Memory GC] 炼化完成！{len(facts)} 条琐碎记忆已折叠为 {len(compacted_texts)} 条核心法则。")

        except Exception as e:
            await db.rollback()
            print(f"[Memory GC] 炼化崩溃: {e}")
