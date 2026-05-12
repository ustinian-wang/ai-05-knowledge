"""可选重排序占位（直接透传）。"""
from __future__ import annotations


def rerank_chunks(question: str, hits: list[dict]) -> list[dict]:
    return hits
