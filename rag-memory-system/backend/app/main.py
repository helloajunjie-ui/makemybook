from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import async_engine, Base
from app.models import MemoryEntity, MemoryFact, StoryPitch, StoryOutlineNode, Book, StoryChapter, StoryChatMessage, StoryApiConfig
from app.routers import memory, ui, pitch, outline, stream, books, chapters, chat, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="RAG Memory System", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memory.router)
app.include_router(ui.router)
app.include_router(pitch.router)
app.include_router(outline.router)
app.include_router(stream.router, prefix="/api/stream", tags=["Stream"])
app.include_router(books.router)
app.include_router(chapters.router)
app.include_router(chat.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok"}
