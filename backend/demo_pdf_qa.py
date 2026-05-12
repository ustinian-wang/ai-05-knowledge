#!/usr/bin/env python3
"""
最小 Demo：内存中生成 PDF → 入库 → RAG 问答。

运行（在 backend 目录且已安装依赖）:
  python demo_pdf_qa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import fitz  # pymupdf

BACKEND_ROOT = Path(__file__).resolve().parent
os.chdir(BACKEND_ROOT)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pipelines.ingest import ingest_file  # noqa: E402
from retrieval.qa import answer_question  # noqa: E402


def main() -> None:
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    pdf_path = Path(path)
    try:
        doc = fitz.open()
        page = doc.new_page()
        body = (
            "本店退换货政策如下。第一点：自签收日起七天内可无理由退货。"
            "第二点：商品需保持原装及配件完整。第三点：定制类商品不支持退货。"
            "如仍有问题，请联系在线客服。祝购物愉快！"
        )
        page.insert_text((72, 72), body, fontsize=12)
        doc.save(str(pdf_path))
        doc.close()

        print("Step 1: ingest PDF -> extract/clean/chunk/embed -> Chroma")
        d = ingest_file(pdf_path, title="退换货政策示例")
        print(f"  doc_id={d.doc_id} title={d.title}")

        q = "定制类商品可以退货吗？"
        print(f"\nStep 2: ask -> embed question -> retrieve TopK -> LLM\n  Q: {q}")
        r = answer_question(q, top_k=3)
        print(f"\nAnswer:\n{r['answer']}\n")
        print(f"Retrieved chunks: {len(r.get('hits') or [])}")
    finally:
        pdf_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
