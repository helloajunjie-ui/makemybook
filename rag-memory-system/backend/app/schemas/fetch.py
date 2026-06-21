from pydantic import BaseModel


class FetchRequest(BaseModel):
    book_id: str
    current_chapter: int
    extracted_triggers: list[str]


class FactItem(BaseModel):
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
