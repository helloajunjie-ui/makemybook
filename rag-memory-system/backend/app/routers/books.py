from typing import Optional
from app.models.chapter import StoryChapter
from app.models.chat import StoryChatMessage
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from app.database import get_db
from app.models.book import Book
from app.models.entity import MemoryEntity
from app.models.fact import MemoryFact
from app.models.pitch import StoryPitch
from app.models.outline import StoryOutlineNode
from app.llm_client import generate_pitches_from_llm, generate_outline_from_llm

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("/")
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).order_by(Book.created_at.desc()))
    books = result.scalars().all()
    return [{
        "id": str(b.id),
        "title": b.title,
        "summary": b.summary,
        "custom_prompt": b.custom_prompt or "",
        "created_at": b.created_at.isoformat() if b.created_at else None
    } for b in books]


@router.get("/{book_id}")
async def get_book(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取单本书详情（含文风约束）"""
    try:
        bid = uuid.UUID(book_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid book ID")
    result = await db.execute(select(Book).where(Book.id == bid))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return {
        "id": str(book.id),
        "title": book.title,
        "summary": book.summary,
        "custom_prompt": book.custom_prompt or "",
        "created_at": book.created_at.isoformat() if book.created_at else None
    }


class CustomPromptUpdate(BaseModel):
    custom_prompt: str = ""


@router.put("/{book_id}/custom_prompt")
async def update_custom_prompt(book_id: str, req: CustomPromptUpdate, db: AsyncSession = Depends(get_db)):
    """💡 持久化书籍专属文风约束到 PostgreSQL"""
    try:
        bid = uuid.UUID(book_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid book ID")
    result = await db.execute(select(Book).where(Book.id == bid))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.custom_prompt = req.custom_prompt
    await db.commit()
    return {"status": "success", "custom_prompt": book.custom_prompt}


class CreateBookRequest(BaseModel):
    title: str
    summary: str = ""


@router.post("/")
async def create_book(req: CreateBookRequest, db: AsyncSession = Depends(get_db)):
    book = Book(title=req.title, summary=req.summary)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return {
        "id": str(book.id),
        "title": book.title,
        "summary": book.summary,
        "created_at": book.created_at.isoformat() if book.created_at else None
    }


class PitchRequest(BaseModel):
    book_id: Optional[str] = None
    seed_text: str
    is_variant: bool = False
    target_pitch: Optional[dict] = None


@router.post("/pitch")
async def api_generate_pitches(req: PitchRequest, request: Request, db: AsyncSession = Depends(get_db)):
    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    pitches = await generate_pitches_from_llm(
        req.seed_text, req.is_variant, req.target_pitch,
        api_key, base_url, model_name
    )
    if not pitches:
        raise HTTPException(status_code=502, detail="LLM API 调用失败，请检查 API 配置、余额或网络连接")

    saved = []
    for p in pitches:
        variant_of = None
        if req.is_variant and req.target_pitch and "id" in req.target_pitch:
            try:
                variant_of = uuid.UUID(str(req.target_pitch["id"]))
            except ValueError:
                pass
        pitch = StoryPitch(
            book_id=uuid.UUID(req.book_id),
            seed_text=req.seed_text,
            variant_of=variant_of,
            title=p.get("title", ""),
            summary=p.get("summary") or p.get("title", ""),
            tone=p.get("tone"),
        )
        db.add(pitch)
        await db.flush()
        saved.append({
            "id": str(pitch.id),
            "title": pitch.title,
            "summary": pitch.summary,
            "tone": pitch.tone,
            "showDetails": False,
        })

    await db.commit()
    return {"status": "success", "data": saved}


class OutlineGenRequest(BaseModel):
    pitch: dict


@router.post("/outline")
async def api_generate_outline(req: OutlineGenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    result = await generate_outline_from_llm(req.pitch, api_key, base_url, model_name)
    if not result.get("outline_nodes"):
        raise HTTPException(status_code=502, detail="LLM API 调用失败，请检查 API 配置、余额或网络连接")

    pitch_id = None
    if "id" in req.pitch:
        try:
            pitch_id = uuid.UUID(str(req.pitch["id"]))
        except ValueError:
            pass

    saved_nodes = []
    for idx, node in enumerate(result["outline_nodes"]):
        outline = StoryOutlineNode(
            pitch_id=pitch_id or uuid.uuid4(),
            volume_number=node.get("volume_number", idx + 1),
            title=node.get("title", ""),
            core_goal=node.get("core_goal"),
            emotion_curve=node.get("emotion_curve"),
            location=node.get("location"),
            estimated_chapters=node.get("estimated_chapters", 5),
            sort_order=idx,
        )
        db.add(outline)
        await db.flush()
        saved_nodes.append({
            "id": str(outline.id),
            "pitch_id": str(outline.pitch_id),
            "volume_number": outline.volume_number,
            "title": outline.title,
            "core_goal": outline.core_goal,
            "emotion_curve": outline.emotion_curve,
            "location": outline.location,
            "estimated_chapters": outline.estimated_chapters,
            "sort_order": outline.sort_order,
        })

    await db.commit()
    return {"status": "success", "data": {"outline_nodes": saved_nodes}}

@router.delete("/{book_id}")
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db)):
    """删除一本书及其所有关联数据（利用数据库级联外键）"""
    try:
        bid = uuid.UUID(book_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid book ID")

    result = await db.execute(select(Book).where(Book.id == bid))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 1. 先删除该 book 下所有 pitch 关联的 outline 节点
    pitch_ids = await db.execute(
        select(StoryPitch.id).where(StoryPitch.book_id == bid)
    )
    for (pid,) in pitch_ids:
        await db.execute(delete(StoryOutlineNode).where(StoryOutlineNode.pitch_id == pid))
    # 2. 删除该 book 下所有 pitch（级联删除由 DB 处理 outline，但 SQLAlchemy 需要手动）
    await db.execute(delete(StoryPitch).where(StoryPitch.book_id == bid))
    # 3. 删除 book（chapter / chat / entity / fact 由数据库级联删除）
    await db.execute(delete(Book).where(Book.id == bid))
    await db.commit()

    return {"status": "success", "message": f"Book {book_id} deleted"}
