"""FastAPI：健康检查、入库、问答。"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import (
    is_spark_gateway,
    load_settings,
    resolved_chat_model,
    settings,
    spark_http_password_configured,
)
from pipelines.documents import list_documents
from pipelines.ingest import ingest_bytes, ingest_file
from retrieval.qa import answer_question


class AskBody(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class IngestPathBody(BaseModel):
    path: str = Field(..., min_length=1)
    title: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="ai-05-knowledge RAG", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        load_settings()
        return {
            "ok": True,
            "project": "ai-05-knowledge",
            "backend_port": settings.backend_port,
            "embedding_model": settings.embedding_model,
            "llm_gateway_spark": is_spark_gateway(),
            "llm_chat_model": resolved_chat_model(),
            "spark_http_api_password_set": spark_http_password_configured(),
        }

    @app.post("/api/v1/rag/ingest")
    async def rag_ingest(
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
    ):
        """上传 PDF/HTML/Markdown，写入向量库。"""
        load_settings()
        data = await file.read()
        doc = ingest_bytes(file.filename or "upload.bin", data, title=title)
        return {"doc_id": doc.doc_id, "title": doc.title, "source": doc.source}

    @app.get("/api/v1/rag/documents")
    def rag_documents():
        """已持久化入库的文档清单（data/docs）。"""
        load_settings()
        return {"items": list_documents()}

    @app.post("/api/v1/rag/ingest_stream")
    async def rag_ingest_stream(
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
    ):
        """上传并以 SSE 推送处理阶段与进度（便于前端进度条）。"""
        load_settings()
        data = await file.read()
        filename = file.filename or "upload.bin"

        q: queue.Queue = queue.Queue()

        def on_progress(stage: str, payload: dict) -> None:
            q.put({"stage": stage, **payload})

        def worker() -> None:
            try:
                ingest_bytes(filename, data, title=title, on_progress=on_progress)
            except Exception as exc:  # noqa: BLE001
                q.put({"stage": "error", "percent": 0, "message": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

        async def event_gen():
            loop = asyncio.get_event_loop()
            while True:
                item = await loop.run_in_executor(None, q.get)
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item.get("stage") in ("done", "error"):
                    break

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/v1/rag/ingest_path")
    def rag_ingest_path(body: IngestPathBody):
        """服务器本地路径入库（便于 demo）。"""
        load_settings()
        doc = ingest_file(Path(body.path), title=body.title)
        return {"doc_id": doc.doc_id, "title": doc.title, "source": doc.source}

    @app.post("/api/v1/rag/ask")
    def rag_ask(body: AskBody):
        load_settings()
        return answer_question(body.question, top_k=body.top_k)

    return app


app = create_app()
