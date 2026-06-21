from pydantic import BaseModel
from datetime import datetime


class OutlineNodeCreate(BaseModel):
    pitch_id: str
    volume_number: int
    title: str
    core_goal: str | None = None
    emotion_curve: str | None = None
    location: str | None = None
    estimated_chapters: int = 5


class OutlineNodeUpdate(BaseModel):
    title: str | None = None
    core_goal: str | None = None
    emotion_curve: str | None = None
    location: str | None = None
    estimated_chapters: int | None = None
    status: str | None = None


class OutlineNodeResponse(BaseModel):
    id: str
    pitch_id: str
    volume_number: int
    title: str
    core_goal: str | None
    emotion_curve: str | None
    location: str | None
    estimated_chapters: int
    status: str
    sort_order: int
    created_at: datetime
