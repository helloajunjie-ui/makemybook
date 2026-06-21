from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from collections import defaultdict

from app.database import get_db
from app.models import MemoryEntity, MemoryFact
from app.schemas.fetch import FetchRequest, FetchResponse, FetchData, EntityItem, FactItem
from app.schemas.commit import CommitRequest
from app.schemas.override import OverrideRequest

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("/fetch", response_model=FetchResponse)
async def predict_fetch_memory(request: FetchRequest, db: AsyncSession = Depends(get_db)):
    extracted = request.extracted_triggers
    if not extracted:
        return FetchResponse(status="success", data=FetchData(found_entries=[], missing_entries=[]))

    stmt = text("""
        SELECT me.id, me.entry_name, me.type, me.triggers,
               mf.id, mf.content, mf.chapter_marker
        FROM memory_entities me
        JOIN memory_facts mf ON mf.entity_id = me.id
        WHERE me.book_id = CAST(:book_id AS uuid)
          AND me.triggers && :triggers
          AND mf.chapter_marker <= :chapter
          AND mf.is_active = true
        ORDER BY me.id, mf.chapter_marker ASC
    """)
    stmt = stmt.bindparams(
        book_id=str(request.book_id),
        triggers=extracted,
        chapter=request.current_chapter
    )

    result = await db.execute(stmt)
    rows = result.all()

    entity_map = {}
    found_triggers_set = set()

    for row in rows:
        me_id, me_name, me_type, me_triggers, mf_id, mf_content, mf_chapter = row

        for t in extracted:
            if t in me_triggers:
                found_triggers_set.add(t)

        if me_id not in entity_map:
            entity_map[me_id] = {
                "entry_name": me_name,
                "type": me_type,
                "facts": []
            }
        entity_map[me_id]["facts"].append(
            FactItem(content=mf_content, chapter_marker=mf_chapter)
        )

    found_entries = [EntityItem(**v) for v in entity_map.values()]
    missing_entries = list(set(extracted) - found_triggers_set)

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
