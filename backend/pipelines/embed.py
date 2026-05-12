"""sentence-transformers 向量化。"""
from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from app.config import settings
from core.models import Chunk, EmbeddingChunk


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    model = _model()
    vectors = model.encode(
        list(texts),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_chunks(chunks: list[Chunk], extra_meta: dict | None = None) -> list[EmbeddingChunk]:
    if not chunks:
        return []
    vecs = embed_texts([c.content for c in chunks])
    out: list[EmbeddingChunk] = []
    base = extra_meta or {}
    for c, v in zip(chunks, vecs, strict=True):
        meta = {
            **base,
            "doc_id": c.doc_id,
            "chunk_id": c.chunk_id,
            "start_offset": c.start_offset,
            "end_offset": c.end_offset,
        }
        out.append(EmbeddingChunk(chunk_id=c.chunk_id, vector=v, metadata=meta))
    return out
