"""RAG 核心数据结构（RawSource / Document / Chunk / EmbeddingChunk）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RawSource(BaseModel):
    """磁盘上的原始文件引用。"""

    source_id: str
    kind: str  # pdf | html | md
    relative_path: str  # 相对 data/raw/


class Document(BaseModel):
    doc_id: str
    title: str
    content: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    start_offset: int
    end_offset: int


class EmbeddingChunk(BaseModel):
    chunk_id: str
    vector: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)
