from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.database import get_db
from app.models.chapter import StoryChapter

router = APIRouter(prefix="/api/chapters", tags=["chapters"])


class SaveChapterRequest(BaseModel):
    book_id: str
    volume_number: int
    chapter_marker: int
    title: str
    content: str


@router.post("/save")
async def save_chapter(req: SaveChapterRequest, db: AsyncSession = Depends(get_db)):
    chapter = StoryChapter(
        book_id=req.book_id,
        volume_number=req.volume_number,
        chapter_marker=req.chapter_marker,
        title=req.title,
        content=req.content,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return {
        "id": str(chapter.id),
        "book_id": str(chapter.book_id),
        "volume_number": chapter.volume_number,
        "chapter_marker": chapter.chapter_marker,
        "title": chapter.title,
        "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
    }


@router.get("/list/{book_id}")
async def list_chapters(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StoryChapter)
        .where(StoryChapter.book_id == book_id)
        .order_by(StoryChapter.volume_number.asc(), StoryChapter.chapter_marker.asc())
    )
    chapters = result.scalars().all()
    return [{
        "id": str(c.id),
        "book_id": str(c.book_id),
        "volume_number": c.volume_number,
        "chapter_marker": c.chapter_marker,
        "title": c.title,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    } for c in chapters]
