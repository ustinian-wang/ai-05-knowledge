"""已入库文档清单（基于 data/docs/*.json）。"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import BACKEND_ROOT


def list_documents() -> list[dict]:
    docs_dir = BACKEND_ROOT / "data" / "docs"
    if not docs_dir.is_dir():
        return []
    rows: list[dict] = []
    for p in sorted(docs_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        doc_id = data.get("doc_id") or p.stem
        chunk_path = BACKEND_ROOT / "data" / "chunks" / f"{doc_id}.json"
        chunk_count = 0
        if chunk_path.is_file():
            try:
                arr = json.loads(chunk_path.read_text(encoding="utf-8"))
                chunk_count = len(arr) if isinstance(arr, list) else 0
            except (OSError, json.JSONDecodeError):
                pass
        st = p.stat()
        rows.append(
            {
                "doc_id": doc_id,
                "title": data.get("title") or "",
                "source": data.get("source") or "",
                "kind": (data.get("metadata") or {}).get("kind"),
                "filename": (data.get("metadata") or {}).get("filename"),
                "chunk_count": chunk_count,
                "updated_at": int(st.st_mtime * 1000),
            }
        )
    return rows
