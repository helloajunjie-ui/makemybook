from pydantic import BaseModel


class CommitRequest(BaseModel):
    book_id: str
    chapter_marker: int
    entry_name: str
    triggers: list[str]
    content: str
    type: str
