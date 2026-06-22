from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# 💡 单机化改造：从 PostgreSQL 降级为 SQLite
# SQLite 无需外部容器，数据库文件直接存储在本地
SQLITE_URL = "sqlite+aiosqlite:///./dream_engine.db"

async_engine = create_async_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False}  # SQLite 多线程访问必需
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
