import json
import math
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from collections import defaultdict

from app.database import get_db
from app.models import MemoryEntity, MemoryFact
from app.schemas.fetch import FetchRequest, FetchResponse, FetchData, EntityItem, FactItem
from app.schemas.commit import CommitRequest
from app.schemas.override import OverrideRequest
from app.llm_client import extract_new_facts, compute_embedding

router = APIRouter(prefix="/api/memory", tags=["memory"])


class RebuildMemoryRequest(BaseModel):
    text: str


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    if not a or not b:
        return 0.0
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _parse_triggers(triggers_raw) -> list:
    """将 triggers 从 Text(JSON) 解析为 list"""
    if isinstance(triggers_raw, list):
        return triggers_raw
    if isinstance(triggers_raw, str):
        try:
            return json.loads(triggers_raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _parse_embedding(embedding_raw) -> list[float] | None:
    """将 embedding 从 Text(JSON) 解析为 list[float]"""
    if isinstance(embedding_raw, list):
        return embedding_raw
    if isinstance(embedding_raw, str):
        try:
            return json.loads(embedding_raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


@router.post("/fetch", response_model=FetchResponse)
async def predict_fetch_memory(request: FetchRequest, db: AsyncSession = Depends(get_db)):
    """
    💡 单机化 RAG 检索：Numpy 内存余弦相似度
    1. 如果 query_text 非空 → 计算 embedding → 内存中计算余弦相似度 → Top 15
    2. 如果 query_text 为空但有 extracted_triggers → triggers JSON 包含匹配
    3. 两者都为空 → 返回本书全量活跃实体
    """
    query_text = request.query_text.strip() if request.query_text else ""
    extracted = request.extracted_triggers

    # ── 查出该书所有活跃的 MemoryFact + Entity ──
    stmt = select(MemoryEntity, MemoryFact).join(
        MemoryFact, MemoryFact.entity_id == MemoryEntity.id
    ).where(
        MemoryEntity.book_id == request.book_id,
        MemoryFact.chapter_marker <= request.current_chapter,
        MemoryFact.is_active == 1
    ).order_by(MemoryEntity.id, MemoryFact.chapter_marker.asc())

    result = await db.execute(stmt)
    rows = result.all()

    entity_map = {}
    found_triggers_set = set()

    # ── 路径 A：向量检索（主路径）──
    if query_text:
        query_embedding = await compute_embedding(query_text)
        if query_embedding:
            # 内存中计算余弦相似度
            scored = []
            for entity, fact in rows:
                fact_emb = _parse_embedding(fact.embedding)
                if fact_emb:
                    score = _cosine_similarity(query_embedding, fact_emb)
                    scored.append((score, entity, fact))

            # 按相似度降序排列，取 Top 15
            scored.sort(key=lambda x: x[0], reverse=True)
            top_rows = scored[:15]

            for score, entity, fact in top_rows:
                me_triggers = _parse_triggers(entity.triggers)
                if extracted:
                    for t in extracted:
                        if t in me_triggers:
                            found_triggers_set.add(t)

                if entity.id not in entity_map:
                    entity_map[entity.id] = {
                        "entry_name": entity.entry_name,
                        "type": entity.type,
                        "triggers": me_triggers,
                        "facts": []
                    }
                entity_map[entity.id]["facts"].append(
                    FactItem(fact_id=str(fact.id), content=fact.content, chapter_marker=fact.chapter_marker)
                )
        else:
            # Embedding API 失败，降级到全量返回
            for entity, fact in rows:
                me_triggers = _parse_triggers(entity.triggers)
                if extracted:
                    for t in extracted:
                        if t in me_triggers:
                            found_triggers_set.add(t)
                if entity.id not in entity_map:
                    entity_map[entity.id] = {
                        "entry_name": entity.entry_name,
                        "type": entity.type,
                        "triggers": me_triggers,
                        "facts": []
                    }
                entity_map[entity.id]["facts"].append(
                    FactItem(fact_id=str(fact.id), content=fact.content, chapter_marker=fact.chapter_marker)
                )

    # ── 路径 B：triggers 包含匹配（旧版兼容）──
    elif extracted:
        for entity, fact in rows:
            me_triggers = _parse_triggers(entity.triggers)
            # 检查是否有任何 extracted trigger 在实体 triggers 中
            matched = any(t in me_triggers for t in extracted)
            if not matched:
                continue
            for t in extracted:
                if t in me_triggers:
                    found_triggers_set.add(t)
            if entity.id not in entity_map:
                entity_map[entity.id] = {
                    "entry_name": entity.entry_name,
                    "type": entity.type,
                    "triggers": me_triggers,
                    "facts": []
                }
            entity_map[entity.id]["facts"].append(
                FactItem(fact_id=str(fact.id), content=fact.content, chapter_marker=fact.chapter_marker)
            )

    # ── 路径 C：全量返回 ──
    else:
        for entity, fact in rows:
            me_triggers = _parse_triggers(entity.triggers)
            if entity.id not in entity_map:
                entity_map[entity.id] = {
                    "entry_name": entity.entry_name,
                    "type": entity.type,
                    "triggers": me_triggers,
                    "facts": []
                }
            entity_map[entity.id]["facts"].append(
                FactItem(fact_id=str(fact.id), content=fact.content, chapter_marker=fact.chapter_marker)
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
                triggers=json.dumps(req.triggers, ensure_ascii=False)
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

        # 💡 透传 LLM 配置参数
        api_key = request.headers.get("X-LLM-API-Key")
        base_url = request.headers.get("X-LLM-Base-URL")
        model_name = request.headers.get("X-LLM-Model")
        extracted_entities = await extract_new_facts(req.text, api_key, base_url, model_name)
        if not extracted_entities:
            await db.commit()
            return {"status": "success", "message": "No new facts extracted."}

        # 💡 4. 植入新记忆
        for item in extracted_entities:
            entry_name = item.get("entry_name", "")
            if not entry_name or len(entry_name) > 12:
                continue

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
                    triggers=json.dumps(triggers, ensure_ascii=False)
                )
                db.add(entity)
                await db.flush()

            # 💡 为新记忆生成 embedding 向量
            fact_content = item.get("content", "")
            fact_embedding = await compute_embedding(fact_content, api_key, base_url)

            new_fact = MemoryFact(
                entity_id=entity.id,
                book_id=book_id,
                content=fact_content,
                chapter_marker=chapter_number,
                embedding=json.dumps(fact_embedding, ensure_ascii=False) if fact_embedding else None
            )
            db.add(new_fact)

        await db.commit()
        return {"status": "success", "message": f"Chapter {chapter_number} memory rebuilt."}

    except Exception as e:
        await db.rollback()
        return {"status": "error", "message": str(e)}
