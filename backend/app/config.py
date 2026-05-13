"""加载 backend/.env；星火 Lite 与 ai-03-writemd / ai-04-pdf 行为对齐。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent

_SPARK_DEFAULT_BASE = "https://spark-api-open.xf-yun.com/v1"

# 与 writemd / ai-04-pdf 并列时，优先用其已验证的星火配置（避免本仓库 .env 里误留 sk- 占位导致合并不进来）
_SIBLING_DOTENV_CANDIDATES: tuple[Path, ...] = (
    BACKEND_ROOT.parent.parent / "ai-03-writemd" / "backend" / ".env",
    BACKEND_ROOT.parent.parent / "ai-04-pdf" / "backend" / ".env",
)


def sanitize_http_bearer_secret(raw: str) -> str:
    """去掉首尾空白、包裹引号、重复的 Bearer 前缀（SDK 会自行加 Bearer）。"""
    s = (raw or "").strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    low = s[:7].lower()
    if low == "bearer ":
        s = s[7:].strip()
    return s


def _key_looks_like_spark_bearer(key: str) -> bool:
    """讯飞 Bearer 常为 APPID:APISecret；与 OpenAI sk-... 区分。"""
    k = key.strip()
    if not k or k.startswith("sk-"):
        return False
    return ":" in k


def _looks_like_spark_route() -> bool:
    """当前环境是否按「走星火网关」配置（用于决定是否用兄弟项目密钥覆盖 sk- 占位）。"""
    base = os.getenv("OPENAI_BASE_URL", "").strip().lower()
    model = os.getenv("OPENAI_MODEL", "").strip().lower()
    if "xf-yun.com" in base:
        return True
    if model == "lite" or model == "spark-x" or model.startswith("spark-"):
        return True
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return _key_looks_like_spark_bearer(key)


def _spark_intent_from_env() -> bool:
    """是否按讯飞星火 HTTP（OpenAI 兼容）使用。"""
    base = os.getenv("OPENAI_BASE_URL", "").strip().lower()
    model = os.getenv("OPENAI_MODEL", "").strip().lower()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if sanitize_http_bearer_secret(os.getenv("SPARK_HTTP_API_PASSWORD", "")):
        return True
    if sanitize_http_bearer_secret(os.getenv("XFYUN_HTTP_API_PASSWORD", "")):
        return True
    return (
        "xf-yun.com" in base
        or model == "lite"
        or model == "spark-x"
        or model.startswith("spark-")
        or _key_looks_like_spark_bearer(key)
    )


def _merge_sibling_dotenv() -> None:
    """
    合并并列项目 backend/.env 中的 OPENAI_* / SPARK_HTTP_*。

    - 默认：本仓库某键为空时，用兄弟项目同名的值填充（与原先 writemd-only 行为一致）。
    - 额外：若判定走星火路由，且本仓库 OPENAI_API_KEY 为 OpenAI 的 sk- 占位，而兄弟项目提供非 sk- 密钥，
      则用兄弟项目的 OPENAI_API_KEY 覆盖（解决「本仓库误留 sk- 导致永远合并不进 writemd 星火 key」）。
    """
    keys = (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "SPARK_HTTP_API_PASSWORD",
        "XFYUN_HTTP_API_PASSWORD",
    )

    merged: dict[str, str] = {}
    for path in _SIBLING_DOTENV_CANDIDATES:
        if not path.is_file():
            continue
        vals = dotenv_values(path)
        for key in keys:
            if key in merged:
                continue
            raw = vals.get(key)
            if raw is None:
                continue
            s = str(raw).strip()
            if s:
                merged[key] = s

    if not merged:
        return

    spark_route = _looks_like_spark_route()
    local_key = os.getenv("OPENAI_API_KEY", "").strip()

    for key, s in merged.items():
        cur = os.getenv(key, "").strip()
        if not cur:
            os.environ[key] = s
            continue
        if (
            key == "OPENAI_API_KEY"
            and spark_route
            and local_key.startswith("sk-")
            and s
            and not s.startswith("sk-")
        ):
            os.environ[key] = s


def _ensure_spark_openai_base() -> None:
    """星火意图且未填 BASE 时补默认网关。"""
    if _spark_intent_from_env() and not os.getenv("OPENAI_BASE_URL", "").strip():
        os.environ["OPENAI_BASE_URL"] = _SPARK_DEFAULT_BASE


def load_settings() -> None:
    load_dotenv(BACKEND_ROOT / ".env", override=True)
    _merge_sibling_dotenv()
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


def spark_chat_api_key() -> str:
    """
    星火 HTTP（OpenAI 兼容）鉴权串：须为控制台「HTTP 服务接口认证」里的 **APIPassword**。

    若仅配置 APPID:APISecret（WebSocket 形态），网关常见报错：apikey not found / HMAC。
    此时请在 .env 设置 SPARK_HTTP_API_PASSWORD=你的 APIPassword（可与 writemd 共用变量名）。
    """
    load_settings()
    for name in ("SPARK_HTTP_API_PASSWORD", "XFYUN_HTTP_API_PASSWORD"):
        v = sanitize_http_bearer_secret(os.getenv(name, ""))
        if v:
            return v
    return sanitize_http_bearer_secret(os.getenv("OPENAI_API_KEY", ""))


def spark_http_password_configured() -> bool:
    """是否已配置专用 HTTP APIPassword（推荐，避免与 WS 密钥混用）。"""
    load_settings()
    return bool(
        sanitize_http_bearer_secret(os.getenv("SPARK_HTTP_API_PASSWORD", ""))
        or sanitize_http_bearer_secret(os.getenv("XFYUN_HTTP_API_PASSWORD", ""))
    )


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
