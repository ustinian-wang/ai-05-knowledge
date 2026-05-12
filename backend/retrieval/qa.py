"""问答流水线：检索 →（可选 rerank）→ 拼 context → LLM。"""
from __future__ import annotations

from openai import OpenAI

from app.config import Settings, load_settings
from retrieval.rerank import rerank_chunks
from retrieval.search import search_chunks


def build_context(hits: list[dict], max_chars: int = 12000) -> str:
    parts: list[str] = []
    used = 0
    for i, h in enumerate(hits, 1):
        title = (h.get("metadata") or {}).get("title") or ""
        block = f"[片段{i}] {title}\n{h.get('content','')}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()


def answer_question(question: str, top_k: int | None = None) -> dict:
    load_settings()
    cfg = Settings()
    hits = search_chunks(question, top_k=top_k)
    hits = rerank_chunks(question, hits)
    context = build_context(hits)
    if not context.strip():
        return {
            "answer": "知识库中暂无相关内容，请先上传 PDF/HTML/Markdown 并完成入库。",
            "context": "",
            "hits": [],
        }

    if not cfg.openai_api_key.strip():
        return {
            "answer": "未配置 OPENAI_API_KEY，以下为检索到的原文片段供人工阅读。",
            "context": context,
            "hits": hits,
        }

    client = OpenAI(
        api_key=cfg.openai_api_key,
        base_url=cfg.openai_base_url or None,
    )
    sys_prompt = (
        "你是严谨的知识库问答助手。请仅依据给定的「参考资料」作答；"
        "若资料不足以回答，请明确说明。使用简体中文，条理清晰。"
    )
    user_prompt = f"参考资料：\n{context}\n\n用户问题：{question}"
    try:
        resp = client.chat.completions.create(
            model=cfg.openai_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        answer = (resp.choices[0].message.content or "").strip()
        return {"answer": answer, "context": context, "hits": hits}
    except Exception as exc:  # noqa: BLE001 — demo 场景下兜底
        return {
            "answer": f"LLM 调用失败（{type(exc).__name__}），请检查 OPENAI_API_KEY / 网关。以下为检索片段。",
            "context": context,
            "hits": hits,
            "error": str(exc),
        }
