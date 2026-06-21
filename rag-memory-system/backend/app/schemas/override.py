from pydantic import BaseModel


class OverrideRequest(BaseModel):
    book_id: str
    fact_id: str
    content: str | None = None
    is_active: int | None = None
