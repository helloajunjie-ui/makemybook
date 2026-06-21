from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.chat import StoryChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SaveMessageRequest(BaseModel):
    book_id: str
    role: str
    type: str
    volume: int | None = None
    chapter: int | None = None
    title: str | None = None
    desc: str | None = None
    content: str | None = None


@router.post("/save")
async def save_message(req: SaveMessageRequest, db: AsyncSession = Depends(get_db)):
    msg = StoryChatMessage(
        book_id=req.book_id,
        role=req.role,
        type=req.type,
        volume=req.volume,
        chapter=req.chapter,
        title=req.title,
        desc=req.desc,
        content=req.content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {"id": str(msg.id)}


@router.get("/list/{book_id}")
async def list_messages(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StoryChatMessage)
        .where(StoryChatMessage.book_id == book_id)
        .order_by(StoryChatMessage.created_at.asc())
    )
    msgs = result.scalars().all()
    return [{
        "id": str(m.id),
        "role": m.role,
        "type": m.type,
        "volume": m.volume,
        "chapter": m.chapter,
        "title": m.title,
        "desc": m.desc,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in msgs]
