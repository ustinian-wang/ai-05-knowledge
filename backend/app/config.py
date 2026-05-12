"""加载 backend/.env 与 RAG 相关配置。"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> None:
    load_dotenv(BACKEND_ROOT / ".env", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    backend_port: int = 8905
    backend_host: str = "127.0.0.1"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_path: str = "vector_db/chroma"
    rag_top_k: int = 5
    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_tokens: int = 80

    @property
    def chroma_dir(self) -> Path:
        p = Path(self.chroma_path)
        return p if p.is_absolute() else (BACKEND_ROOT / p)


load_settings()
settings = Settings()
