"""ingest 总流程：extract → clean → Document → chunk → embed → Chroma。"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import chromadb

from app.config import BACKEND_ROOT, settings
from core.models import Document, RawSource
from pipelines.chunk import build_chunks
from pipelines.clean import clean_text
from pipelines.embed import embed_chunks
from pipelines.extract import extract_from_raw


def _ensure_dirs() -> None:
    for sub in ("raw", "parsed", "docs", "chunks"):
        (BACKEND_ROOT / "data" / sub).mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)


def _detect_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".html", ".htm"):
        return "html"
    if ext in (".md", ".markdown"):
        return "md"
    raise ValueError(f"unsupported extension: {ext}")


def _chroma_collection():
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )


def ingest_file(source_path: Path, title: str | None = None) -> Document:
    """
    将本地文件写入 data/raw，跑完整流水线并写入向量库。
    返回最终 Document。
    """
    _ensure_dirs()
    kind = _detect_kind(source_path)
    doc_id = uuid.uuid4().hex[:12]
    ext = source_path.suffix.lower() or ".txt"
    rel_raw = f"{doc_id}{ext}"
    raw_path = BACKEND_ROOT / "data" / "raw" / rel_raw
    shutil.copy2(source_path, raw_path)

    raw = RawSource(source_id=doc_id, kind=kind, relative_path=rel_raw)
    extracted = extract_from_raw(raw, BACKEND_ROOT)
    cleaned = clean_text(extracted)

    parsed_path = BACKEND_ROOT / "data" / "parsed" / f"{doc_id}.txt"
    parsed_path.write_text(cleaned, encoding="utf-8")

    doc_title = title or source_path.stem
    doc = Document(
        doc_id=doc_id,
        title=doc_title,
        content=cleaned,
        source=str(raw_path.relative_to(BACKEND_ROOT)),
        metadata={"kind": kind, "filename": source_path.name},
    )
    doc_path = BACKEND_ROOT / "data" / "docs" / f"{doc_id}.json"
    doc_path.write_text(doc.model_dump_json(ensure_ascii=False, indent=2), encoding="utf-8")

    chunks = build_chunks(doc_id, cleaned)
    chunks_path = BACKEND_ROOT / "data" / "chunks" / f"{doc_id}.json"
    chunks_path.write_text(
        json.dumps([c.model_dump() for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    coll = _chroma_collection()
    embs = embed_chunks(
        chunks,
        extra_meta={"title": doc_title, "source": doc.source},
    )
    if embs:
        coll.upsert(
            ids=[e.chunk_id for e in embs],
            embeddings=[e.vector for e in embs],
            documents=[c.content for c in chunks],
            metadatas=[e.metadata for e in embs],
        )

    return doc


def ingest_bytes(filename: str, data: bytes, title: str | None = None) -> Document:
    """用于上传：先落临时文件再 ingest。"""
    tmp = BACKEND_ROOT / "data" / "raw" / f"_tmp_{uuid.uuid4().hex}{Path(filename).suffix}"
    tmp.write_bytes(data)
    try:
        return ingest_file(tmp, title=title or Path(filename).stem)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
