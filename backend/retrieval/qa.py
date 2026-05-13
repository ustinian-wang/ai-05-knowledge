"""问答流水线：检索 →（可选 rerank）→ 拼 context → LLM。"""
from __future__ import annotations

import os

from openai import OpenAI

from app.config import (
    Settings,
    is_spark_gateway,
    load_settings,
    normalize_openai_base_url,
    resolved_chat_model,
    settings,
    spark_chat_api_key,
    spark_http_password_configured,
)
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
    k = top_k or settings.rag_top_k
    # 多取候选再重排，减轻「单一大 PDF」占满 TopK 的情况
    pool = min(max(k * 4, 24), 80)
    raw = search_chunks(question, top_k=pool)
    hits = rerank_chunks(question, raw, keep=k)
    context = build_context(hits)
    if not context.strip():
        return {
            "answer": "知识库中暂无相关内容，请先上传 PDF/HTML/Markdown 并完成入库。",
            "context": "",
            "hits": [],
        }

    api_key = spark_chat_api_key() if is_spark_gateway() else cfg.openai_api_key.strip()
    if not api_key:
        if is_spark_gateway():
            msg = (
                "未配置可用的星火 HTTP 密钥：请在 backend/.env 设置 "
                "SPARK_HTTP_API_PASSWORD=控制台「HTTP 服务接口认证」中的 APIPassword，"
                "或让 OPENAI_API_KEY 仅填该密码（勿填 APPID:APISecret）。以下为检索片段。"
            )
        else:
            msg = "未配置 OPENAI_API_KEY，以下为检索到的原文片段供人工阅读。"
        return {"answer": msg, "context": context, "hits": hits}

    base_raw = (cfg.openai_base_url or "").strip() or None
    client = OpenAI(
        api_key=api_key,
        base_url=normalize_openai_base_url(base_raw),
    )
    chat_model = resolved_chat_model()
    sys_prompt = (
        "你是严谨的知识库问答助手。请仅依据给定的「参考资料」作答；"
        "若资料不足以回答，请明确说明。使用简体中文，条理清晰。"
    )
    user_prompt = f"参考资料：\n{context}\n\n用户问题：{question}"
    try:
        req: dict = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        # 星火 HTTP 文档示例含 user；缺省时部分网关统计异常，补固定客户端 id
        if is_spark_gateway():
            uid = os.getenv("SPARK_CHAT_USER", "ai-05-knowledge-rag").strip()[:64]
            if uid:
                req["user"] = uid
        resp = client.chat.completions.create(**req)
        answer = (resp.choices[0].message.content or "").strip()
        return {"answer": answer, "context": context, "hits": hits}
    except Exception as exc:  # noqa: BLE001 — demo 场景下兜底
        err = str(exc)
        spark_hint = ""
        if "apikey not found" in err or "HMAC" in err:
            spark_hint = (
                " 星火侧未认可当前 Bearer：HTTP 兼容接口必须使用控制台「HTTP 服务接口认证」里的 **APIPassword**"
                "（单列字符串），不要填 WebSocket 用的 APPID:APISecret。"
                "请在 backend/.env 增加一行：SPARK_HTTP_API_PASSWORD=你的APIPassword（可与 ai-03-writemd 相同），"
                "保留 OPENAI_MODEL=lite，重启 uvicorn。"
            )
            if not spark_http_password_configured() and ":" in (api_key or ""):
                spark_hint += " 检测到密钥含冒号，极可能为 WS 形态，请务必改用 SPARK_HTTP_API_PASSWORD。"
        return {
            "answer": (
                f"LLM 调用失败（{type(exc).__name__}），请检查 OPENAI_API_KEY、"
                "OPENAI_BASE_URL（星火可留空由程序补全）及 OPENAI_MODEL（Lite 用 lite）。"
                "以下为检索片段。"
                f"{spark_hint}"
            ),
            "context": context,
            "hits": hits,
            "error": err,
        }
