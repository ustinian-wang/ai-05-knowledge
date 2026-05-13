# ai-05-knowledge

**网站内容 AI 问答（RAG）** 沙箱：PDF / HTML / Markdown 入库 → 切块 → `sentence-transformers` 向量 → **Chroma** 持久化 → 检索 + **OpenAI 兼容** LLM 作答。

与 `projects/ai-01-chat` 等一致：**`backend/`（FastAPI）** + **`frontend/`（Vite + Vue 3）**；密钥写在 **`backend/.env`**（勿提交），可参考 **`backend/.env.example`**。

### 讯飞星火 Lite（HTTP / OpenAI 兼容）

与 **`ai-03-writemd`**、**`ai-04-pdf`** 对齐：

- **`OPENAI_API_KEY`**：走星火 HTTP 时，应填控制台 **「HTTP 服务接口认证」** 中的 **APIPassword**（单列）。**不要**把 WebSocket 的 `APPID:APISecret` 当作 Bearer，否则易 401 / `apikey not found`。
- **推荐**：单独配置 **`SPARK_HTTP_API_PASSWORD=你的APIPassword`**（本仓库问答会**优先**读它）；也可用别名 **`XFYUN_HTTP_API_PASSWORD`**。
- **`OPENAI_BASE_URL`**：可留空；走星火时程序会设为 `https://spark-api-open.xf-yun.com/v1`。
- **`OPENAI_MODEL`**：Lite 使用 **`lite`**。
- **可选**：**`SPARK_CHAT_USER`** 作为请求体 `user` 字段（默认 `ai-05-knowledge-rag`），便于网关侧统计。
- **自动合并**：本仓库某键为空时，会按顺序合并 **`projects/ai-03-writemd/backend/.env`**、**`projects/ai-04-pdf/backend/.env`** 中的 **`OPENAI_*` / `SPARK_HTTP_*` / `XFYUN_HTTP_*`**。若当前为 **Lite/星火路由**，但本仓库 **`OPENAI_API_KEY` 误留 `sk-...` 占位**，会用兄弟项目中 **非 `sk-` 的 `OPENAI_API_KEY`** 覆盖，避免「其它项目能调星火、这里却 401」。

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
│   ├── ingest.py     # 总入口：extract → clean → document → chunk → embed → Chroma（支持 on_progress）
│   ├── documents.py  # 已入库文档清单（供 API）
│   ├── extract.py    # PDF(PyMuPDF) / HTML(trafilatura+bs4) / MD
│   ├── clean.py      # 空白与换行规范化
│   ├── chunk.py      # 按「等效 token」预算切块（本地 approx，不依赖 tiktoken 联网）
│   └── embed.py      # sentence-transformers 向量
├── retrieval/
│   ├── search.py     # Chroma 余弦检索
│   ├── rerank.py     # 词面加权（中日文 bigram / 英文词）+ 低信息片段降权
│   └── qa.py         # 扩大候选池 → rerank → 拼 context → LLM
├── vector_db/chroma/ # Chroma 持久化目录（.gitignore）
├── api/app.py        # FastAPI 路由
├── app/main.py       # uvicorn 入口（导出 app）
└── demo_pdf_qa.py    # 最小可运行 PDF → QA 示例
```

## 数据流

**入库 `ingest_pipeline`**

1. **Raw**：文件保存到 `data/raw/{doc_id}.{ext}`，并记录 `RawSource`（支持 **`.pdf`、`.html`/`.htm`、`.md`/`.markdown`**）。
2. **Extract**：`extract.py` 按类型抽取正文（网页走 trafilatura，失败则 BeautifulSoup 降级）。
3. **Clean**：`clean.py` 压缩多余空白与空行。
4. **Document**：写入 `data/docs/{doc_id}.json`（`doc_id/title/content/source/metadata`）。
5. **Chunk**：`chunk.py` 用 **`approx_token_count`** 估算长度，按句号优先切句，再按配置的 min/max/overlap 组装 `Chunk`（offset 相对正文），写入 `data/chunks/{doc_id}.json`。
6. **Embed**：`embed.py` 对每段文本生成向量，组装 `EmbeddingChunk`。
7. **Store**：`chromadb` 集合 `knowledge_base` 中 `upsert`（cosine）。

**问答 `query_pipeline`**

1. 对 **用户问题** 做与文档相同的 embedding。
2. Chroma **query** 先取较大 **候选池**（约 `max(top_k×4, 24)`，上限 80），再经 **`rerank_chunks`** 截断为请求的 `top_k`，减轻单一大文档占满结果的问题。
3. `qa.py` 将命中片段拼成 **context**，调用 Chat Completions；星火网关下会附带 **`user`**。若无 Key 或调用失败，则返回检索文本与错误提示（含常见 `apikey not found` 的排查说明）。

## 前端（`frontend/`）

- 开发默认 **http://127.0.0.1:9175**，通过 Vite 代理调用后端。
- **文档列表**、**上传**（`accept` 与后端格式一致）、**SSE 入库进度**（`/api/v1/rag/ingest_stream`）、**问答区**（问/答卡片、可折叠参考片段与调试信息）。

## 开发

```bash
cd projects/ai-05-knowledge/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填写密钥；可选 OPENAI_BASE_URL / OPENAI_MODEL / SPARK_HTTP_API_PASSWORD
uvicorn app.main:app --host 127.0.0.1 --port 8905

cd ../frontend
npm install && npm run dev
# 浏览器：默认 http://127.0.0.1:9175
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查；含 `embedding_model`、`llm_gateway_spark`、`llm_chat_model`、`spark_http_api_password_set` 等 |
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
