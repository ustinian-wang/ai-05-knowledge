"""按 token 预算切块：500~1000 token、overlap 50~100，优先在句号处断开。

使用本地启发式估算 token 数，避免 tiktoken 首次联网下载编码表。
"""
from __future__ import annotations

import re

from app.config import settings
from core.models import Chunk


def approx_token_count(text: str) -> int:
    """粗略估算 token 数（中英文混合场景下与 cl100k 量级接近即可）。"""
    if not text:
        return 0
    n = len(text)
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(n, 1)
    # 英文约 4 字符/token，中文约 1.5~2 字符/token
    factor = 0.25 * ascii_ratio + 0.62 * (1 - ascii_ratio)
    return max(1, int(n * factor))


def split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def sentence_spans_in_content(content: str, sentences: list[str]) -> list[tuple[int, int]]:
    """将句子映射回 content 中的 [start, end) 区间（顺序扫描）。"""
    spans: list[tuple[int, int]] = []
    pos = 0
    for s in sentences:
        idx = content.find(s, pos)
        if idx < 0:
            idx = content.find(s)
        if idx < 0:
            continue
        spans.append((idx, idx + len(s)))
        pos = idx + len(s)
    return spans


def build_chunks(doc_id: str, content: str) -> list[Chunk]:
    min_t = settings.chunk_min_tokens
    max_t = settings.chunk_max_tokens
    ov = max(0, settings.chunk_overlap_tokens)

    sentences = split_sentences(content)
    spans = sentence_spans_in_content(content, sentences)
    if not spans:
        if content.strip():
            return [
                Chunk(
                    chunk_id=f"{doc_id}_0000",
                    doc_id=doc_id,
                    content=content.strip(),
                    start_offset=0,
                    end_offset=len(content),
                )
            ]
        return []

    chunks: list[Chunk] = []
    idx_chunk = 0
    i = 0

    while i < len(spans):
        start = spans[i][0]
        j = i
        end = spans[j][1]
        token_count = approx_token_count(content[start:end])

        while j + 1 < len(spans):
            n_start, n_end = spans[j + 1]
            cand = content[start:n_end]
            cand_tokens = approx_token_count(cand)
            if cand_tokens > max_t:
                if token_count >= min_t:
                    break
                j += 1
                end = n_end
                token_count = cand_tokens
                break
            j += 1
            end = n_end
            token_count = cand_tokens
            if token_count >= max_t:
                break

        piece = content[start:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}_{idx_chunk:04d}",
                    doc_id=doc_id,
                    content=piece,
                    start_offset=start,
                    end_offset=end,
                )
            )
            idx_chunk += 1

        if j + 1 >= len(spans):
            break

        tail_start = start
        if ov > 0:
            for t in range(end - 1, start - 1, -1):
                tail = content[t:end]
                if approx_token_count(tail) >= ov:
                    tail_start = t
                    break

        next_i = j + 1
        for k in range(j, i - 1, -1):
            if spans[k][0] >= tail_start:
                next_i = k
            else:
                break
        if next_i <= i:
            next_i = i + 1
        if next_i >= len(spans):
            break
        i = next_i

    return chunks
