from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.outline import StoryOutlineNode
from app.schemas.outline import OutlineNodeCreate, OutlineNodeUpdate, OutlineNodeResponse

router = APIRouter(prefix="/api/outline", tags=["outline"])


@router.post("/create", response_model=OutlineNodeResponse)
async def create_node(req: OutlineNodeCreate, db: AsyncSession = Depends(get_db)):
    node = StoryOutlineNode(
        pitch_id=req.pitch_id,
        volume_number=req.volume_number,
        title=req.title,
        core_goal=req.core_goal,
        emotion_curve=req.emotion_curve,
        location=req.location,
        estimated_chapters=req.estimated_chapters
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return _to_response(node)


@router.get("/list/{pitch_id}", response_model=list[OutlineNodeResponse])
async def list_nodes(pitch_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StoryOutlineNode)
        .where(StoryOutlineNode.pitch_id == pitch_id)
        .order_by(StoryOutlineNode.sort_order.asc())
    )
    nodes = result.scalars().all()
    return [_to_response(n) for n in nodes]


# 💡【P1-5 修复】通过 book_id 查大纲（绕过 pitch_id 依赖）
# outline → pitch → book 链路：StoryOutlineNode.pitch_id → StoryPitch.id → StoryPitch.book_id
@router.get("/by-book/{book_id}", response_model=list[OutlineNodeResponse])
async def list_nodes_by_book(book_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.pitch import StoryPitch
    result = await db.execute(
        select(StoryOutlineNode)
        .join(StoryPitch, StoryOutlineNode.pitch_id == StoryPitch.id)
        .where(StoryPitch.book_id == book_id)
        .order_by(StoryOutlineNode.sort_order.asc())
    )
    nodes = result.scalars().all()
    return [_to_response(n) for n in nodes]


@router.put("/update/{node_id}", response_model=OutlineNodeResponse)
async def update_node(node_id: str, req: OutlineNodeUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StoryOutlineNode).where(StoryOutlineNode.id == node_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        return {"status": "error", "message": "node not found"}

    if req.title is not None:
        node.title = req.title
    if req.core_goal is not None:
        node.core_goal = req.core_goal
    if req.emotion_curve is not None:
        node.emotion_curve = req.emotion_curve
    if req.location is not None:
        node.location = req.location
    if req.estimated_chapters is not None:
        node.estimated_chapters = req.estimated_chapters
    if req.status is not None:
        node.status = req.status

    await db.commit()
    await db.refresh(node)
    return _to_response(node)


def _to_response(n: StoryOutlineNode) -> OutlineNodeResponse:
    return OutlineNodeResponse(
        id=str(n.id),
        pitch_id=str(n.pitch_id),
        volume_number=n.volume_number,
        title=n.title,
        core_goal=n.core_goal,
        emotion_curve=n.emotion_curve,
        location=n.location,
        estimated_chapters=n.estimated_chapters,
        status=n.status,
        sort_order=n.sort_order,
        created_at=n.created_at
    )
