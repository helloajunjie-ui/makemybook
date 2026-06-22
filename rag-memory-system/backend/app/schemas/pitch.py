from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class PitchCreate(BaseModel):
    book_id: Optional[str] = None
    seed_text: str
    title: str
    summary: str
    tone: Optional[str] = None
    variant_of: Optional[str] = None


class PitchResponse(BaseModel):
    id: str
    book_id: str = ""
    seed_text: str
    variant_of: Optional[str] = None
    title: str
    summary: str
    tone: Optional[str] = None
    is_selected: int
    created_at: datetime


class PitchSelect(BaseModel):
    pitch_id: str
