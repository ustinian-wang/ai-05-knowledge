"""清洗抽取后的纯文本。"""
from __future__ import annotations

import re


def clean_text(text: str) -> str:
    if not text:
        return ""
    # 统一换行、压缩连续空白
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()
