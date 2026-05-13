<template>
  <div class="wrap">
    <h1>ai-05-knowledge · RAG</h1>
    <p class="hint">界面模式：深色单栏（与默认沙箱一致）</p>

    <section class="card">
      <h2>健康检查</h2>
      <pre class="pre">{{ healthText }}</pre>
    </section>

    <section class="card">
      <h2>已入库文件</h2>
      <p class="hint">数据来自服务端 <code>data/docs</code>，刷新可同步最新列表。</p>
      <button class="btn" type="button" :disabled="loadingDocs" @click="loadDocuments">刷新列表</button>
      <div v-if="loadingDocs" class="hint row-gap">加载中…</div>
      <div v-else-if="!documents.length" class="hint row-gap">暂无文档，请先上传。</div>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th>标题</th>
            <th>类型</th>
            <th>分块数</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in documents" :key="d.doc_id">
            <td class="td-title" :title="d.source">{{ d.title || d.doc_id }}</td>
            <td>{{ d.kind || '—' }}</td>
            <td>{{ d.chunk_count }}</td>
            <td class="td-mono">{{ formatTime(d.updated_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>入库（带处理进度）</h2>
      <input type="file" accept=".pdf,.html,.htm,.md,.markdown" @change="onFile" />
      <button class="btn" type="button" :disabled="ingesting || !file" @click="ingestStream">
        上传并入库（流式进度）
      </button>
      <div v-if="ingesting || progressPercent > 0" class="progress-wrap row-gap">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }" />
        </div>
        <div class="progress-label">{{ progressPercent }}% · {{ lastStage }}</div>
      </div>
      <ul v-if="progressLines.length" class="log">
        <li v-for="(line, i) in progressLines" :key="i">{{ line }}</li>
      </ul>
      <div v-if="ingestSummary" class="ingest-done row-gap">
        <div class="ingest-done-title">入库完成</div>
        <div class="ingest-done-row"><span class="k">文档</span>{{ ingestSummary.title }}</div>
        <div class="ingest-done-row"><span class="k">doc_id</span><code>{{ ingestSummary.doc_id }}</code></div>
        <div class="ingest-done-row"><span class="k">路径</span><code class="break-all">{{ ingestSummary.source }}</code></div>
      </div>
      <div v-else-if="ingestErrText" class="alert alert-err row-gap">{{ ingestErrText }}</div>
    </section>

    <section class="card qa-card">
      <h2>问答</h2>
      <textarea v-model="question" rows="3" class="ta" placeholder="输入问题" />
      <button class="btn" type="button" :disabled="asking" @click="ask">提问</button>

      <div v-if="asking" class="qa-loading row-gap">正在检索知识库并生成回答…</div>

      <div v-else-if="askFetchError" class="alert alert-err row-gap">{{ askFetchError }}</div>

      <div v-else-if="askResult" class="qa-body row-gap">
        <div v-if="askResult.error" class="alert alert-warn">
          <div class="alert-title">模型调用未成功</div>
          <p class="alert-p">{{ shortError(askResult.error) }}</p>
        </div>

        <div class="qa-q">
          <span class="qa-badge">问</span>
          <p class="qa-q-text">{{ askResult._question }}</p>
        </div>

        <div class="qa-a-block">
          <span class="qa-badge qa-badge-a">答</span>
          <div class="qa-answer">{{ askResult.answer || '（无正文）' }}</div>
        </div>

        <details v-if="askResult.hits && askResult.hits.length" class="qa-details">
          <summary>参考片段（{{ askResult.hits.length }} 条）</summary>
          <div
            v-for="(h, idx) in askResult.hits"
            :key="idx"
            class="hit-card"
          >
            <div class="hit-head">
              <span class="hit-no">#{{ idx + 1 }}</span>
              <span class="hit-title">{{ hitTitle(h) }}</span>
              <span v-if="hitDist(h) != null" class="hit-dist">相似度距离 {{ hitDist(h) }}</span>
            </div>
            <div class="hit-snippet">{{ hitSnippet(h) }}</div>
          </div>
        </details>

        <details v-if="askResult.context" class="qa-details qa-details-muted">
          <summary>拼接上下文（调试用）</summary>
          <div class="context-box">{{ askResult.context }}</div>
        </details>
      </div>
    </section>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      healthText: '加载中…',
      documents: [],
      loadingDocs: false,
      file: null,
      ingesting: false,
      progressPercent: 0,
      lastStage: '',
      progressLines: [],
      ingestSummary: null,
      ingestErrText: '',
      question: '定制类商品可以退货吗？',
      /** @type {null | { answer: string, context?: string, hits?: any[], error?: string, _question: string }} */
      askResult: null,
      askFetchError: '',
      asking: false,
    };
  },
  mounted() {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        this.healthText = JSON.stringify(d, null, 2);
      })
      .catch((e) => {
        this.healthText = String(e);
      });
    this.loadDocuments();
  },
  methods: {
    formatTime(ms) {
      if (!ms) return '—';
      try {
        return new Date(ms).toLocaleString();
      } catch {
        return String(ms);
      }
    },
    hitTitle(h) {
      const m = h && h.metadata;
      return (m && m.title) || '未命名文档';
    },
    hitDist(h) {
      const d = h && h.distance;
      return typeof d === 'number' ? d.toFixed(4) : null;
    },
    hitSnippet(h) {
      const t = (h && h.content) || '';
      const max = 480;
      if (t.length <= max) return t;
      return `${t.slice(0, max)}…`;
    },
    shortError(err) {
      const s = String(err || '');
      return s.length > 360 ? `${s.slice(0, 360)}…` : s;
    },
    loadDocuments() {
      this.loadingDocs = true;
      fetch('/api/v1/rag/documents')
        .then((r) => r.json())
        .then((d) => {
          this.documents = (d && d.items) || [];
        })
        .catch(() => {
          this.documents = [];
        })
        .finally(() => {
          this.loadingDocs = false;
        });
    },
    onFile(ev) {
      const f = ev.target.files && ev.target.files[0];
      this.file = f || null;
    },
    pushLog(obj) {
      const stage = obj.stage || '';
      const pct = obj.percent != null ? `${obj.percent}%` : '';
      const msg = obj.message || '';
      const extra = [];
      if (obj.chunk_count != null) extra.push(`chunks=${obj.chunk_count}`);
      if (obj.kind) extra.push(`kind=${obj.kind}`);
      const line = [stage, pct, msg, extra.join(' ')].filter(Boolean).join(' · ');
      this.progressLines.push(line);
      if (this.progressLines.length > 30) this.progressLines.shift();
    },
    async ingestStream() {
      if (!this.file) {
        this.ingestErrText = '请先选择文件';
        this.ingestSummary = null;
        return;
      }
      this.ingesting = true;
      this.progressPercent = 0;
      this.lastStage = '';
      this.progressLines = [];
      this.ingestSummary = null;
      this.ingestErrText = '';

      const fd = new FormData();
      fd.append('file', this.file);
      fd.append('title', this.file.name);

      try {
        const res = await fetch('/api/v1/rag/ingest_stream', { method: 'POST', body: fd });
        if (!res.ok) {
          this.ingestErrText = `上传失败：HTTP ${res.status}`;
          return;
        }
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split('\n\n');
          buf = parts.pop() || '';
          for (const block of parts) {
            for (const line of block.split('\n')) {
              if (!line.startsWith('data: ')) continue;
              let evt;
              try {
                evt = JSON.parse(line.slice(6));
              } catch {
                continue;
              }
              if (evt.percent != null) this.progressPercent = evt.percent;
              this.lastStage = evt.stage || '';
              this.pushLog(evt);
              if (evt.stage === 'done') {
                this.ingestSummary = {
                  doc_id: evt.doc_id,
                  title: evt.title,
                  source: evt.source,
                };
              }
              if (evt.stage === 'error') {
                this.ingestErrText = evt.message || JSON.stringify(evt);
              }
            }
          }
        }
      } catch (e) {
        this.ingestErrText = String(e);
      } finally {
        this.ingesting = false;
        this.loadDocuments();
      }
    },
    ask() {
      const q = (this.question || '').trim();
      if (!q) {
        this.askFetchError = '请输入问题';
        this.askResult = null;
        return;
      }
      this.asking = true;
      this.askFetchError = '';
      this.askResult = null;
      fetch('/api/v1/rag/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: 5 }),
      })
        .then(async (r) => {
          if (!r.ok) {
            const t = await r.text();
            throw new Error(t || `HTTP ${r.status}`);
          }
          return r.json();
        })
        .then((d) => {
          this.askResult = {
            answer: d.answer || '',
            context: d.context || '',
            hits: Array.isArray(d.hits) ? d.hits : [],
            error: d.error || '',
            _question: q,
          };
        })
        .catch((e) => {
          this.askFetchError = String(e);
        })
        .finally(() => {
          this.asking = false;
        });
    },
  },
};
</script>

<style>
body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #0f1220;
  color: #e8ecff;
}
.wrap {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px;
}
.hint {
  color: #9aa3c7;
  font-size: 13px;
}
.row-gap {
  margin-top: 12px;
}
.pre {
  background: #151a2e;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  white-space: pre-wrap;
}
.card {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid #2a3152;
  border-radius: 10px;
}
.btn {
  margin-left: 8px;
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  background: #4f6dff;
  color: #fff;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ta {
  width: 100%;
  margin: 8px 0;
  background: #151a2e;
  color: #e8ecff;
  border: 1px solid #2a3152;
  border-radius: 8px;
  padding: 8px;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
  font-size: 14px;
}
.tbl th,
.tbl td {
  border: 1px solid #2a3152;
  padding: 8px 10px;
  text-align: left;
}
.tbl th {
  background: #151a2e;
  color: #b8c0e8;
}
.td-title {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.td-mono {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.progress-wrap {
  max-width: 480px;
}
.progress-bar {
  height: 8px;
  background: #151a2e;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #2a3152;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f6dff, #7c9bff);
  transition: width 0.2s ease;
}
.progress-label {
  margin-top: 6px;
  font-size: 13px;
  color: #9aa3c7;
}
.log {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #c5cae8;
  font-size: 13px;
  max-height: 200px;
  overflow: auto;
}
code {
  background: #151a2e;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.break-all {
  word-break: break-all;
}
.ingest-done {
  padding: 12px 14px;
  background: #151a2e;
  border-radius: 10px;
  border: 1px solid #2f3758;
}
.ingest-done-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #b8c7ff;
}
.ingest-done-row {
  font-size: 13px;
  margin-top: 4px;
  line-height: 1.5;
}
.ingest-done-row .k {
  display: inline-block;
  min-width: 4.5em;
  color: #8b95b8;
  margin-right: 6px;
}
.qa-card .qa-loading {
  color: #9aa3c7;
  font-size: 14px;
}
.alert {
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.5;
}
.alert-err {
  background: rgba(255, 82, 82, 0.12);
  border: 1px solid rgba(255, 120, 120, 0.35);
  color: #ffb4b4;
}
.alert-warn {
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.35);
  color: #ffe08a;
  margin-bottom: 16px;
}
.alert-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.alert-p {
  margin: 0;
  font-size: 13px;
  opacity: 0.95;
}
.qa-q {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #151a2e;
  border-radius: 10px;
  border: 1px solid #2a3152;
}
.qa-q-text {
  margin: 0;
  flex: 1;
  line-height: 1.55;
  white-space: pre-wrap;
}
.qa-badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background: #2a3152;
  color: #b8c0e8;
}
.qa-badge-a {
  background: #3d4a8f;
  color: #e8ecff;
}
.qa-a-block {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.qa-answer {
  flex: 1;
  margin: 0;
  padding: 14px 16px;
  background: #1a2038;
  border-radius: 10px;
  border: 1px solid #343d64;
  line-height: 1.7;
  font-size: 15px;
  white-space: pre-wrap;
  color: #eef1ff;
}
.qa-details {
  margin-top: 16px;
  border: 1px solid #2a3152;
  border-radius: 10px;
  padding: 8px 12px;
  background: #12162a;
}
.qa-details summary {
  cursor: pointer;
  color: #9aa3c7;
  font-size: 13px;
  padding: 4px 0;
}
.qa-details-muted summary {
  color: #6c7699;
}
.hit-card {
  margin-top: 12px;
  padding: 10px 12px;
  background: #151a2e;
  border-radius: 8px;
  border: 1px solid #2a3152;
}
.hit-card:first-of-type {
  margin-top: 8px;
}
.hit-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  color: #9aa3c7;
  margin-bottom: 6px;
}
.hit-no {
  color: #7c86a8;
  font-variant-numeric: tabular-nums;
}
.hit-title {
  color: #c5cae8;
  font-weight: 500;
}
.hit-dist {
  margin-left: auto;
  color: #6c7699;
}
.hit-snippet {
  font-size: 13px;
  line-height: 1.55;
  color: #c8d0f0;
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.context-box {
  margin-top: 8px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #8b95b8;
  background: #0f1220;
  border-radius: 8px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
