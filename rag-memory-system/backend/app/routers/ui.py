from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import MemoryEntity, MemoryFact

router = APIRouter(prefix="/api/ui", tags=["ui"])


@router.get("/entities")
def list_entities(book_id: str = Query(...), db: Session = Depends(get_db)):
    entities = db.query(MemoryEntity).filter(
        MemoryEntity.book_id == book_id
    ).order_by(MemoryEntity.entry_name).all()
    return [{
        "id": str(e.id),
        "entry_name": e.entry_name,
        "type": e.type,
        "triggers": e.triggers
    } for e in entities]


@router.get("/facts")
def list_facts(book_id: str = Query(...), entity_id: str | None = None, chapter: int | None = None, db: Session = Depends(get_db)):
    q = db.query(MemoryFact).join(MemoryEntity).filter(
        MemoryEntity.book_id == book_id,
        MemoryFact.is_active == 1
    )
    if entity_id:
        q = q.filter(MemoryFact.entity_id == entity_id)
    if chapter is not None:
        q = q.filter(MemoryFact.chapter_marker <= chapter)
    facts = q.order_by(MemoryFact.chapter_marker.asc()).all()
    return [{
        "id": str(f.id),
        "entity_id": str(f.entity_id),
        "chapter_marker": f.chapter_marker,
        "content": f.content
    } for f in facts]


@router.get("/chapters")
def get_chapters(book_id: str = Query(...), db: Session = Depends(get_db)):
    result = db.query(
        MemoryFact.chapter_marker,
        func.count(MemoryFact.id)
    ).join(MemoryEntity).filter(
        MemoryEntity.book_id == book_id,
        MemoryFact.is_active == 1
    ).group_by(
        MemoryFact.chapter_marker
    ).order_by(
        MemoryFact.chapter_marker.asc()
    ).all()
    return [{"chapter": r[0], "fact_count": r[1]} for r in result]
