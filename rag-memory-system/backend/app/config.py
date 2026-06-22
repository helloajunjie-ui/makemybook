from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./dream_engine.db"
    embedding_dim: int = 1536
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
