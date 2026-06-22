from pydantic import BaseModel
from typing import Optional


class FetchRequest(BaseModel):
    book_id: str
    current_chapter: int
    extracted_triggers: list[str] = []  # 兼容旧版（不再使用）
    query_text: str = ""  # 💡 RAG v2：原始文本，后端做向量检索


class FactItem(BaseModel):
    fact_id: str = ""
    content: str
    chapter_marker: int


class EntityItem(BaseModel):
    entry_name: str
    type: str
    triggers: list[str] = []
    facts: list[FactItem]


class FetchData(BaseModel):
    found_entries: list[EntityItem]
    missing_entries: list[str]


class FetchResponse(BaseModel):
    status: str
    data: FetchData
