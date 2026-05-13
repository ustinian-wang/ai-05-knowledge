"""向量检索：query embedding + Chroma cosine TopK。"""
from __future__ import annotations

import chromadb

from app.config import settings
from pipelines.embed import embed_texts


def get_collection():
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )


def search_chunks(question: str, top_k: int | None = None) -> list[dict]:
    """从向量库取候选片段；top_k 为「实际拉取条数」，问答侧可先放大再 rerank 截断。"""
    k = top_k or settings.rag_top_k
    coll = get_collection()
    count = coll.count()
    if count == 0:
        return []
    qvec = embed_texts([question])[0]
    res = coll.query(
        query_embeddings=[qvec],
        n_results=min(max(k, 1), count),
        include=["documents", "metadatas", "distances"],
    )
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    dists = res.get("distances") or [[]]
    out: list[dict] = []
    for text, meta, dist in zip(docs[0], metas[0], dists[0], strict=True):
        out.append({"content": text, "metadata": meta or {}, "distance": dist})
    return out
