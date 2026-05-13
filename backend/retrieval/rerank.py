"""轻量重排：中文词面命中加权 + 低信息片段降权，缓解「单一大文档」压制其它材料。"""
from __future__ import annotations

import re


def _cjk_chars(s: str) -> str:
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def _question_terms(question: str) -> tuple[list[str], list[str]]:
    """返回 (二字片段, 单字) 用于词面匹配。"""
    s = _cjk_chars(question)
    bigrams: list[str] = []
    if len(s) >= 2:
        bigrams = [s[i : i + 2] for i in range(len(s) - 1)]
    # 去重保序
    seen: set[str] = set()
    bg2: list[str] = []
    for b in bigrams:
        if b not in seen:
            seen.add(b)
            bg2.append(b)
    singles = list(dict.fromkeys(list(s)))
    return bg2, singles


def _low_signal_text(text: str) -> bool:
    """正文几乎无有效汉字（多为点阵/目录线），向量噪声大。"""
    sample = (text or "")[:1200]
    if not sample.strip():
        return True
    cjk = sum(1 for c in sample if "\u4e00" <= c <= "\u9fff")
    if cjk < 8:
        return True
    dot_like = sum(1 for c in sample if c in "·.\u00b7\u2022")
    return dot_like / max(len(sample), 1) > 0.35


def rerank_chunks(question: str, hits: list[dict], keep: int | None = None) -> list[dict]:
    """
    在向量距离基础上做词面加分（距离越小越好 → 用 adjusted 排序）。
    keep 为 None 时返回与输入等长（兼容旧调用）。
    """
    if not hits:
        return []
    bigrams, singles = _question_terms(question)
    scored: list[tuple[float, dict]] = []

    for h in hits:
        meta = h.get("metadata") or {}
        title = str(meta.get("title") or "")
        body = str(h.get("content") or "")
        hay = f"{title}\n{body}"
        dist = float(h.get("distance") if h.get("distance") is not None else 1.0)

        bonus = 0.0
        for bg in bigrams[:24]:
            if bg and bg in hay:
                bonus += 0.018
        for ch in singles[:16]:
            if ch in hay:
                bonus += 0.0025

        if _low_signal_text(body):
            bonus -= 0.12

        # 英文/数字问题：简单 token 命中
        for w in re.findall(r"[A-Za-z0-9]{3,}", question):
            if w.lower() in hay.lower():
                bonus += 0.012

        bonus = max(-0.2, min(bonus, 0.28))
        adjusted = dist - bonus
        scored.append((adjusted, h))

    scored.sort(key=lambda x: x[0])
    out = [h for _, h in scored]
    if keep is not None:
        out = out[: max(keep, 0)]
    return out
