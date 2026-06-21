from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.pitch import StoryPitch
from app.schemas.pitch import PitchCreate, PitchResponse, PitchSelect

router = APIRouter(prefix="/api/pitch", tags=["pitch"])


@router.post("/create", response_model=PitchResponse)
async def create_pitch(req: PitchCreate, db: AsyncSession = Depends(get_db)):
    pitch = StoryPitch(
        book_id=uuid.UUID(req.book_id),
        seed_text=req.seed_text,
        variant_of=uuid.UUID(req.variant_of) if req.variant_of else None,
        title=req.title,
        summary=req.summary,
        tone=req.tone
    )
    db.add(pitch)
    await db.commit()
    await db.refresh(pitch)
    return PitchResponse(
        id=str(pitch.id),
        book_id=str(pitch.book_id),
        seed_text=pitch.seed_text,
        variant_of=str(pitch.variant_of) if pitch.variant_of else None,
        title=pitch.title,
        summary=pitch.summary,
        tone=pitch.tone,
        is_selected=pitch.is_selected,
        created_at=pitch.created_at
    )


@router.get("/list", response_model=list[PitchResponse])
async def list_pitches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StoryPitch).order_by(StoryPitch.created_at.desc())
    )
    pitches = result.scalars().all()
    return [PitchResponse(
        id=str(p.id),
        book_id=str(p.book_id),
        seed_text=p.seed_text,
        variant_of=str(p.variant_of) if p.variant_of else None,
        title=p.title,
        summary=p.summary,
        tone=p.tone,
        is_selected=p.is_selected,
        created_at=p.created_at
    ) for p in pitches]


@router.put("/select")
async def select_pitch(req: PitchSelect, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StoryPitch))
    all_pitches = result.scalars().all()
    for p in all_pitches:
        p.is_selected = 1 if str(p.id) == req.pitch_id else 0
    await db.commit()
    return {"status": "ok"}
