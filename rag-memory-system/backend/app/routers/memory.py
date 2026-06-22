from fastapi import APIRouter, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, delete
from sqlalchemy import Float
from collections import defaultdict
import uuid

from app.database import get_db
from app.models import MemoryEntity, MemoryFact
from app.schemas.fetch import FetchRequest, FetchResponse, FetchData, EntityItem, FactItem
from app.schemas.commit import CommitRequest
from app.schemas.override import OverrideRequest
from app.llm_client import extract_new_facts, compute_embedding

router = APIRouter(prefix="/api/memory", tags=["memory"])


class RebuildMemoryRequest(BaseModel):
    text: str


@router.post("/fetch", response_model=FetchResponse)
async def predict_fetch_memory(request: FetchRequest, db: AsyncSession = Depends(get_db)):
    """
    💡 RAG v2 混合检索：
    1. 如果 query_text 非空 → 计算 embedding → cosine_distance 向量检索（Top 15）
    2. 如果 query_text 为空但有 extracted_triggers → 传统 triggers && 数组重叠
    3. 两者都为空 → 返回本书全量活跃实体
    """
    query_text = request.query_text.strip() if request.query_text else ""
    extracted = request.extracted_triggers

    # ── 路径 A：向量检索（RAG v2 主路径）──
    if query_text:
        # 计算 query embedding
        query_embedding = await compute_embedding(query_text)
        if query_embedding:
            # pgvector cosine_distance 语义搜索
            stmt = text("""
                SELECT me.id, me.entry_name, me.type, me.triggers,
                       mf.id, mf.content, mf.chapter_marker,
                       mf.embedding <=> :query_vec AS distance
                FROM memory_entities me
                JOIN memory_facts mf ON mf.entity_id = me.id
                WHERE me.book_id = CAST(:book_id AS uuid)
                  AND mf.chapter_marker <= :chapter
                  AND mf.is_active = 1
                  AND mf.embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT 15
            """)
            stmt = stmt.bindparams(
                book_id=str(request.book_id),
                chapter=request.current_chapter,
                query_vec=query_embedding
            )
        else:
            # Embedding API 失败，降级到全量返回
            stmt = text("""
                SELECT me.id, me.entry_name, me.type, me.triggers,
                       mf.id, mf.content, mf.chapter_marker,
                       0.0 AS distance
                FROM memory_entities me
                JOIN memory_facts mf ON mf.entity_id = me.id
                WHERE me.book_id = CAST(:book_id AS uuid)
                  AND mf.chapter_marker <= :chapter
                  AND mf.is_active = 1
                ORDER BY me.id, mf.chapter_marker ASC
            """)
            stmt = stmt.bindparams(
                book_id=str(request.book_id),
                chapter=request.current_chapter
            )

    # ── 路径 B：triggers 数组重叠（旧版兼容）──
    elif extracted:
        stmt = text("""
            SELECT me.id, me.entry_name, me.type, me.triggers,
                   mf.id, mf.content, mf.chapter_marker,
                   0.0 AS distance
            FROM memory_entities me
            JOIN memory_facts mf ON mf.entity_id = me.id
            WHERE me.book_id = CAST(:book_id AS uuid)
              AND me.triggers && :triggers
              AND mf.chapter_marker <= :chapter
              AND mf.is_active = 1
            ORDER BY me.id, mf.chapter_marker ASC
        """)
        stmt = stmt.bindparams(
            book_id=str(request.book_id),
            triggers=extracted,
            chapter=request.current_chapter
        )

    # ── 路径 C：全量返回 ──
    else:
        stmt = text("""
            SELECT me.id, me.entry_name, me.type, me.triggers,
                   mf.id, mf.content, mf.chapter_marker,
                   0.0 AS distance
            FROM memory_entities me
            JOIN memory_facts mf ON mf.entity_id = me.id
            WHERE me.book_id = CAST(:book_id AS uuid)
              AND mf.chapter_marker <= :chapter
              AND mf.is_active = 1
            ORDER BY me.id, mf.chapter_marker ASC
        """)
        stmt = stmt.bindparams(
            book_id=str(request.book_id),
            chapter=request.current_chapter
        )

    result = await db.execute(stmt)
    rows = result.all()

    entity_map = {}
    found_triggers_set = set()

    for row in rows:
        me_id, me_name, me_type, me_triggers, mf_id, mf_content, mf_chapter, _distance = row

        # triggers 重叠匹配（仅用于 missing_entries 统计）
        if extracted:
            for t in extracted:
                if t in (me_triggers or []):
                    found_triggers_set.add(t)

        if me_id not in entity_map:
            entity_map[me_id] = {
                "entry_name": me_name,
                "type": me_type,
                "triggers": me_triggers or [],
                "facts": []
            }
        entity_map[me_id]["facts"].append(
            FactItem(fact_id=str(mf_id), content=mf_content, chapter_marker=mf_chapter)
        )

    found_entries = [EntityItem(**v) for v in entity_map.values()]
    missing_entries = list(set(extracted) - found_triggers_set) if extracted else []

    return FetchResponse(
        status="success",
        data=FetchData(found_entries=found_entries, missing_entries=missing_entries)
    )


@router.post("/commit")
async def commit_memory(req: CommitRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(MemoryEntity).where(
                MemoryEntity.book_id == req.book_id,
                MemoryEntity.entry_name == req.entry_name
            )
        )
        entity = result.scalar_one_or_none()

        if entity is None:
            entity = MemoryEntity(
                book_id=req.book_id,
                entry_name=req.entry_name,
                type=req.type,
                triggers=req.triggers
            )
            db.add(entity)
            await db.flush()

        fact = MemoryFact(
            entity_id=entity.id,
            book_id=req.book_id,
            chapter_marker=req.chapter_marker,
            content=req.content
        )
        db.add(fact)
        await db.commit()
        return {"status": "ok", "fact_id": str(fact.id)}
    except Exception:
        await db.rollback()
        return {"status": "error", "message": "commit failed"}


@router.put("/override")
async def override_fact(req: OverrideRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MemoryFact).where(MemoryFact.id == req.fact_id)
    )
    fact = result.scalar_one_or_none()

    if fact is None:
        return {"status": "error", "message": "fact not found"}

    if req.content is not None:
        fact.content = req.content
    if req.is_active is not None:
        fact.is_active = req.is_active

    await db.commit()
    return {"status": "ok"}


@router.post("/{book_id}/rebuild/{chapter_number}")
async def rebuild_chapter_memory(
    book_id: str,
    chapter_number: int,
    req: RebuildMemoryRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    时间线覆写引擎：精准抹除某章旧记忆，重塑新记忆
    当用户在时光机面板修改/重写某章后调用，防止"祖父悖论"
    """
    try:
        # 💡 1. 抹除旧痕迹：删除该章节产生的所有 MemoryFact
        await db.execute(
            delete(MemoryFact).where(
                MemoryFact.book_id == book_id,
                MemoryFact.chapter_marker == chapter_number
            )
        )
        await db.flush()

        # 💡 2. 清理幽灵实体：删除没有任何事实关联的孤立实体
        # 查出该书中所有实体
        all_entities = await db.execute(
            select(MemoryEntity).where(MemoryEntity.book_id == book_id)
        )
        for entity in all_entities.scalars().all():
            fact_count = await db.execute(
                select(MemoryFact).where(MemoryFact.entity_id == entity.id).limit(1)
            )
            if fact_count.first() is None:
                await db.delete(entity)

        await db.flush()

        # 💡【P2-6 修复】透传 LLM 配置参数，防止后台静默重塑时认证失败
        api_key = request.headers.get("X-LLM-API-Key")
        base_url = request.headers.get("X-LLM-Base-URL")
        model_name = request.headers.get("X-LLM-Model")
        extracted_entities = await extract_new_facts(req.text, api_key, base_url, model_name)
        if not extracted_entities:
            await db.commit()
            return {"status": "success", "message": "No new facts extracted."}

        # 💡 4. 植入新记忆（复用 stream.py 的入库逻辑）
        for item in extracted_entities:
            entry_name = item.get("entry_name", "")
            if not entry_name or len(entry_name) > 12:
                continue

            # 查找或创建实体
            result = await db.execute(
                select(MemoryEntity).where(
                    MemoryEntity.book_id == book_id,
                    MemoryEntity.entry_name == entry_name
                )
            )
            entity = result.scalar_one_or_none()

            if entity is None:
                triggers = item.get("triggers", [])
                if not isinstance(triggers, list):
                    triggers = []
                if entry_name not in triggers:
                    triggers.append(entry_name)

                entity = MemoryEntity(
                    book_id=book_id,
                    entry_name=entry_name,
                    type=item.get("type", "其他"),
                    triggers=triggers
                )
                db.add(entity)
                await db.flush()

            # 💡 RAG v2：为新记忆生成 embedding 向量
            fact_content = item.get("content", "")
            fact_embedding = await compute_embedding(fact_content, api_key, base_url)

            # 插入新的事实（标记为当前被修改的章节）
            new_fact = MemoryFact(
                entity_id=entity.id,
                book_id=book_id,
                content=fact_content,
                chapter_marker=chapter_number,
                embedding=fact_embedding if fact_embedding else None
            )
            db.add(new_fact)

        await db.commit()
        return {"status": "success", "message": f"Chapter {chapter_number} memory rebuilt."}

    except Exception as e:
        await db.rollback()
        return {"status": "error", "message": str(e)}
