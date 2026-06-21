from pydantic import BaseModel
from datetime import datetime


class PitchCreate(BaseModel):
    seed_text: str
    title: str
    summary: str
    tone: str | None = None
    variant_of: str | None = None


class PitchResponse(BaseModel):
    id: str
    seed_text: str
    variant_of: str | None
    title: str
    summary: str
    tone: str | None
    is_selected: int
    created_at: datetime


class PitchSelect(BaseModel):
    pitch_id: str
