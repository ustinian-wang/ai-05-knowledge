"""从 PDF / HTML / Markdown 抽取正文。"""
from __future__ import annotations

from pathlib import Path

import fitz  # pymupdf
import trafilatura
from bs4 import BeautifulSoup

from core.models import RawSource


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def extract_pdf(path: Path) -> str:
    """使用 PyMuPDF 抽取 PDF 文本。"""
    text_parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text") or "")
    return "\n".join(text_parts).strip()


def extract_html(path: Path) -> str:
    """优先 trafilatura 主文抽取，失败时用 BeautifulSoup 降级为可见文本。"""
    raw = _read_bytes(path)
    try:
        text = trafilatura.extract(raw.decode("utf-8", errors="ignore"), url=None)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def extract_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def extract_from_raw(raw: RawSource, backend_root: Path) -> str:
    full = backend_root / "data" / "raw" / raw.relative_path
    if raw.kind == "pdf":
        return extract_pdf(full)
    if raw.kind == "html":
        return extract_html(full)
    if raw.kind == "md":
        return extract_markdown(full)
    raise ValueError(f"unsupported kind: {raw.kind}")
