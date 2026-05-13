"""加载 backend/.env；星火 Lite 与 ai-03-writemd / ai-04-pdf 行为对齐。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent

_SPARK_DEFAULT_BASE = "https://spark-api-open.xf-yun.com/v1"


def _key_looks_like_spark_bearer(key: str) -> bool:
    """讯飞 Bearer 常为 APPID:APISecret；与 OpenAI sk-... 区分。"""
    k = key.strip()
    if not k or k.startswith("sk-"):
        return False
    return ":" in k


def _spark_intent_from_env() -> bool:
    """是否按讯飞星火 HTTP（OpenAI 兼容）使用。"""
    base = os.getenv("OPENAI_BASE_URL", "").strip().lower()
    model = os.getenv("OPENAI_MODEL", "").strip().lower()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return (
        "xf-yun.com" in base
        or model == "lite"
        or model == "spark-x"
        or model.startswith("spark-")
        or _key_looks_like_spark_bearer(key)
    )


def _merge_writemd_openai_if_needed() -> None:
    """本仓库 .env 中 OPENAI_* 为空时，尝试合并并列 ai-03-writemd 的 .env。"""
    sibling = BACKEND_ROOT.parent.parent / "ai-03-writemd" / "backend" / ".env"
    if not sibling.is_file():
        return
    vals = dotenv_values(sibling)
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        if os.getenv(key, "").strip():
            continue
        raw = vals.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            os.environ[key] = s


def _ensure_spark_openai_base() -> None:
    """星火意图且未填 BASE 时补默认网关。"""
    if _spark_intent_from_env() and not os.getenv("OPENAI_BASE_URL", "").strip():
        os.environ["OPENAI_BASE_URL"] = _SPARK_DEFAULT_BASE


def load_settings() -> None:
    load_dotenv(BACKEND_ROOT / ".env", override=True)
    _merge_writemd_openai_if_needed()
    _ensure_spark_openai_base()


def is_spark_gateway() -> bool:
    load_settings()
    return "xf-yun.com" in os.getenv("OPENAI_BASE_URL", "").strip().lower()


def normalize_openai_base_url(url: str | None) -> str | None:
    """OpenAI SDK 建议 base_url 带末尾 /。"""
    if not url or not str(url).strip():
        return None
    u = str(url).strip().rstrip("/")
    return f"{u}/"


def resolved_chat_model() -> str:
    """问答用模型名：未配置时星火走 lite，否则 gpt-4o-mini。"""
    load_settings()
    m = os.getenv("OPENAI_MODEL", "").strip()
    if m:
        return m
    if is_spark_gateway():
        return "lite"
    return "gpt-4o-mini"


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
