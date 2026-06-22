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
    pitch_id: Optional[str] = None  # 💡 认亲手术：前端传入选中的 Pitch ID


@router.post("/")
async def create_book(req: CreateBookRequest, db: AsyncSession = Depends(get_db)):
    book = Book(title=req.title, summary=req.summary)
    db.add(book)
    await db.flush()  # 用 flush 而非 commit，拿到 book.id 后继续操作

    # 💡 认亲手术：将孤儿 Pitch 绑定到新创建的 Book
    if req.pitch_id:
        try:
            pitch_uuid = uuid.UUID(str(req.pitch_id))
            pitch = await db.get(StoryPitch, pitch_uuid)
            if pitch:
                pitch.book_id = book.id
                print(f"[认亲手术] Pitch {pitch.id} 的 book_id 已绑定为 {book.id}")
            else:
                print(f"[认亲手术] 未找到 pitch_id={req.pitch_id}，尝试按 title 兜底")
                # 兜底：按 title 匹配
                row = await db.execute(
                    select(StoryPitch).where(
                        StoryPitch.book_id.is_(None),
                        StoryPitch.title == req.title
                    ).order_by(StoryPitch.created_at.desc()).limit(1)
                )
                fallback = row.scalar_one_or_none()
                if fallback:
                    fallback.book_id = book.id
                    print(f"[认亲手术-兜底] Pitch {fallback.id} 的 book_id 已绑定为 {book.id}")
        except Exception as e:
            print(f"[认亲手术] 绑定失败（非致命）: {e}")
    else:
        # 无 pitch_id 时按 title 兜底（兼容旧流程）
        try:
            row = await db.execute(
                select(StoryPitch).where(
                    StoryPitch.book_id.is_(None),
                    StoryPitch.title == req.title
                ).order_by(StoryPitch.created_at.desc()).limit(1)
            )
            pitch = row.scalar_one_or_none()
            if pitch:
                pitch.book_id = book.id
                print(f"[认亲手术-兜底] Pitch {pitch.id} 的 book_id 已绑定为 {book.id}")
        except Exception as e:
            print(f"[认亲手术-兜底] 绑定失败（非致命）: {e}")

    await db.commit()
    await db.refresh(book)
    return {
        "id": str(book.id),
        "title": book.title,
        "summary": book.summary,
        "custom_prompt": book.custom_prompt or "",
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

        # 💡 契约修复：始终持久化 Pitch，即使尚无 book_id
        # 首次创建 Pitch 时 book_id 为 NULL，后续 create_book 会回写
        try:
            book_id_uuid = uuid.UUID(req.book_id) if req.book_id else None
            pitch = StoryPitch(
                book_id=book_id_uuid,
                seed_text=req.seed_text,
                variant_of=variant_of,
                title=p.get("title", ""),
                summary=p.get("summary") or p.get("title", ""),
                tone=p.get("tone"),
                details=p.get("details", ""),
            )
            db.add(pitch)
            await db.flush()
            saved.append({
                "id": str(pitch.id),
                "title": pitch.title,
                "summary": pitch.summary,
                "tone": pitch.tone,
                "details": p.get("details", ""),
                "showDetails": False,
            })
        except Exception as e:
            print(f"[Pitch持久化] 失败（降级返回）: {e}")
            saved.append({
                "id": "",
                "title": p.get("title", ""),
                "summary": p.get("summary") or p.get("title", ""),
                "tone": p.get("tone"),
                "details": p.get("details", ""),
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
    if "id" in req.pitch and req.pitch["id"]:
        try:
            pitch_id = uuid.UUID(str(req.pitch["id"]))
        except ValueError:
            pass

    # 💡 防御性兜底：如果 pitch_id 仍为空，按 title 查找已持久化的 Pitch
    if not pitch_id:
        try:
            title = req.pitch.get("title", "")
            if title:
                row = await db.execute(
                    select(StoryPitch).where(
                        StoryPitch.title == title
                    ).order_by(StoryPitch.created_at.desc()).limit(1)
                )
                found = row.scalar_one_or_none()
                if found:
                    pitch_id = found.id
                    print(f"[大纲] 按 title 匹配到 Pitch: {found.id}")
        except Exception as e:
            print(f"[大纲] 防御性查找 Pitch 失败: {e}")

    if not pitch_id:
        raise HTTPException(status_code=400, detail="Pitch ID is required — pitch was not persisted correctly")

    saved_nodes = []
    for idx, node in enumerate(result["outline_nodes"]):
        outline = StoryOutlineNode(
            pitch_id=pitch_id,
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
            "status": "pending",
        })

    await db.commit()
    return {"status": "success", "data": {"outline_nodes": saved_nodes}}

@router.delete("/{book_id}")
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db)):
    """删除一本书及其所有关联数据"""
    try:
        bid = uuid.UUID(book_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid book ID")

    result = await db.execute(select(Book).where(Book.id == bid))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 1. 删除该 book 下所有 pitch 关联的 outline 节点
    pitch_ids = await db.execute(
        select(StoryPitch.id).where(StoryPitch.book_id == bid)
    )
    for (pid,) in pitch_ids:
        await db.execute(delete(StoryOutlineNode).where(StoryOutlineNode.pitch_id == pid))
    # 2. 删除该 book 下所有 pitch
    await db.execute(delete(StoryPitch).where(StoryPitch.book_id == bid))
    # 3. 删除 chapters（无外键约束，需手动）
    await db.execute(delete(StoryChapter).where(StoryChapter.book_id == bid))
    # 4. 删除 chat messages（无外键约束，需手动）
    await db.execute(delete(StoryChatMessage).where(StoryChatMessage.book_id == bid))
    # 5. 删除 book（entity / fact 由数据库级联删除）
    await db.execute(delete(Book).where(Book.id == bid))
    await db.commit()

    return {"status": "success", "message": f"Book {book_id} deleted"}


@router.delete("/clean/all")
async def clean_all_data(db: AsyncSession = Depends(get_db)):
    """清空所有数据（管理用：一键重置）"""
    await db.execute(delete(StoryOutlineNode))
    await db.execute(delete(StoryPitch))
    await db.execute(delete(StoryChapter))
    await db.execute(delete(StoryChatMessage))
    await db.execute(delete(MemoryFact))
    await db.execute(delete(MemoryEntity))
    await db.execute(delete(Book))
    await db.commit()
    return {"status": "success", "message": "All data cleared"}
