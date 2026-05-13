# ai-05-knowledge

**网站内容 AI 问答（RAG）** 沙箱：PDF / HTML / Markdown 入库 → 切块 → `sentence-transformers` 向量 → **Chroma** 持久化 → 检索 + **OpenAI 兼容** LLM 作答。

与 `projects/ai-01-chat` 等一致：**`backend/`（FastAPI）** + **`frontend/`（Vite）**；密钥写在 **`backend/.env`**（勿提交）。

### 讯飞星火 Lite（HTTP / OpenAI 兼容）

与 **`ai-03-writemd`**、**`ai-04-pdf`** 对齐：

- **`OPENAI_API_KEY`**：走星火 HTTP 时，应填控制台 **「HTTP 服务接口认证」** 中的 **APIPassword**（单列）。**不要**把 WebSocket 的 `APPID:APISecret` 当作 Bearer，否则易 401 / `apikey not found`。
- **推荐**：单独配置 **`SPARK_HTTP_API_PASSWORD=你的APIPassword`**（本仓库问答会**优先**读它，可与 writemd 对齐）；若并列存在 `projects/ai-03-writemd/backend/.env` 且本仓库未配，会自动合并该变量。
- **`OPENAI_BASE_URL`**：可留空；走星火时程序会设为 `https://spark-api-open.xf-yun.com/v1`。
- **`OPENAI_MODEL`**：Lite 使用 **`lite`**。
- 本仓库 **`OPENAI_*` / `SPARK_HTTP_API_PASSWORD` 为空** 时，会尝试从并列目录 **`projects/ai-03-writemd/backend/.env`** 合并同名变量，便于与本机已有 writemd 配置共用。

官方说明见讯飞开放平台「星火认知大模型 HTTP 调用」文档；向量仍用本机 **sentence-transformers**，不向星火请求 embedding。

## 目录（后端）

```
backend/
├── data/
│   ├── raw/          # 原始上传/拷贝文件
│   ├── parsed/       # 清洗后纯文本（调试用）
│   ├── docs/         # Document JSON
│   └── chunks/       # Chunk 列表 JSON
├── pipelines/
│   ├── ingest.py     # 总入口：extract → clean → document → chunk → embed → Chroma
│   ├── extract.py    # PDF(PyMuPDF) / HTML(trafilatura+bs4) / MD
│   ├── clean.py      # 空白与换行规范化
│   ├── chunk.py      # 500~1000「等效 token」、overlap、按句切分
│   └── embed.py      # sentence-transformers 向量
├── retrieval/
│   ├── search.py     # TopK 余弦检索（Chroma）
│   ├── rerank.py     # 可选重排（当前透传）
│   └── qa.py         # 拼 context + LLM
├── vector_db/chroma/ # Chroma 持久化目录（.gitignore）
├── api/app.py        # FastAPI 路由
├── app/main.py       # uvicorn 入口（导出 app）
└── demo_pdf_qa.py    # 最小可运行 PDF → QA 示例
```

## 数据流

**入库 `ingest_pipeline`**

1. **Raw**：文件保存到 `data/raw/{doc_id}.{ext}`，并记录 `RawSource`。
2. **Extract**：`extract.py` 按类型抽取正文（网页走 trafilatura，失败则 BeautifulSoup 降级）。
3. **Clean**：`clean.py` 压缩多余空白与空行。
4. **Document**：写入 `data/docs/{doc_id}.json`（`doc_id/title/content/source/metadata`）。
5. **Chunk**：`chunk.py` 按句号优先切句，再按配置的 min/max/overlap 组装 `Chunk`（offset 相对正文），写入 `data/chunks/{doc_id}.json`。
6. **Embed**：`embed.py` 对每段文本生成向量，组装 `EmbeddingChunk`。
7. **Store**：`chromadb` 集合 `knowledge_base` 中 `upsert`（cosine）。

**问答 `query_pipeline`**

1. 对 **用户问题** 做与文档相同的 embedding。
2. Chroma **query**，取 TopK（默认 5，可在请求体覆盖）。
3. 可选 `rerank.py`（当前原样返回）。
4. `qa.py` 将命中片段拼成 **context**，调用 Chat Completions；若无 Key 或调用失败，则返回检索文本供人工阅读。

## 开发

```bash
cd projects/ai-05-knowledge/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填写 OPENAI_API_KEY；可选 OPENAI_BASE_URL / OPENAI_MODEL
uvicorn app.main:app --host 127.0.0.1 --port 8905

cd ../frontend
npm install && npm run dev
# 浏览器：默认 http://127.0.0.1:9175
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/v1/rag/documents` | 已入库文档清单（`data/docs` + 分块数） |
| POST | `/api/v1/rag/ingest` | `multipart/form-data`：`file` + 可选 `title` |
| POST | `/api/v1/rag/ingest_stream` | 同上，响应 **`text/event-stream`（SSE）**，`data:` JSON 含 `stage` / `percent` / `message` |
| POST | `/api/v1/rag/ingest_path` | JSON：`{"path":"/abs/path/file.pdf","title":"可选"}`（本机调试） |
| POST | `/api/v1/rag/ask` | JSON：`{"question":"...","top_k":5}` |

## 最小 Demo（PDF → QA）

```bash
cd projects/ai-05-knowledge/backend
source .venv/bin/activate
# 可不配置 Key：将只返回检索片段
OPENAI_API_KEY= python demo_pdf_qa.py
```

## Git

本目录为**独立仓库**：在 `projects/ai-05-knowledge` 内执行 `git remote add` / `git push`。

共性说明见仓库根目录 `docs/ai-projects-family.md`。
