from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.apiconfig import StoryApiConfig

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class PresetItem(BaseModel):
    preset_name: str
    api_key: str
    base_url: str
    model: str


class SaveSettingsRequest(BaseModel):
    active_preset: str
    presets: list[PresetItem]


class SettingsResponse(BaseModel):
    active_preset: str
    presets: list[PresetItem]


@router.get("/load")
async def load_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StoryApiConfig))
    rows = result.scalars().all()
    presets = []
    active_preset = "deepseek"
    for r in rows:
        presets.append(PresetItem(
            preset_name=r.preset_name,
            api_key=r.api_key,
            base_url=r.base_url,
            model=r.model,
        ))
        if r.is_active:
            active_preset = r.preset_name
    return SettingsResponse(active_preset=active_preset, presets=presets)


@router.post("/save")
async def save_settings(req: SaveSettingsRequest, db: AsyncSession = Depends(get_db)):
    for p in req.presets:
        result = await db.execute(
            select(StoryApiConfig).where(StoryApiConfig.preset_name == p.preset_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.api_key = p.api_key
            existing.base_url = p.base_url
            existing.model = p.model
            existing.is_active = 1 if p.preset_name == req.active_preset else 0
        else:
            db.add(StoryApiConfig(
                preset_name=p.preset_name,
                api_key=p.api_key,
                base_url=p.base_url,
                model=p.model,
                is_active=1 if p.preset_name == req.active_preset else 0,
            ))
    await db.commit()
    return {"status": "ok"}
