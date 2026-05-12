"""FastAPI：健康检查、入库、问答。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import load_settings, settings
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
