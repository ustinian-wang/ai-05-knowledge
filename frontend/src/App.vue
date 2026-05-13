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
      <pre v-if="ingestResultText" class="pre row-gap">{{ ingestResultText }}</pre>
    </section>

    <section class="card">
      <h2>问答</h2>
      <textarea v-model="question" rows="3" class="ta" placeholder="输入问题" />
      <button class="btn" type="button" :disabled="asking" @click="ask">提问</button>
      <pre class="pre">{{ askText }}</pre>
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
      ingestResultText: '',
      question: '定制类商品可以退货吗？',
      askText: '',
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
        this.ingestResultText = '请先选择文件';
        return;
      }
      this.ingesting = true;
      this.progressPercent = 0;
      this.lastStage = '';
      this.progressLines = [];
      this.ingestResultText = '';

      const fd = new FormData();
      fd.append('file', this.file);
      fd.append('title', this.file.name);

      try {
        const res = await fetch('/api/v1/rag/ingest_stream', { method: 'POST', body: fd });
        if (!res.ok) {
          this.ingestResultText = `HTTP ${res.status}`;
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
                this.ingestResultText = JSON.stringify(evt, null, 2);
              }
              if (evt.stage === 'error') {
                this.ingestResultText = JSON.stringify(evt, null, 2);
              }
            }
          }
        }
      } catch (e) {
        this.ingestResultText = String(e);
      } finally {
        this.ingesting = false;
        this.loadDocuments();
      }
    },
    ask() {
      this.asking = true;
      this.askText = '请求中…';
      fetch('/api/v1/rag/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: this.question, top_k: 5 }),
      })
        .then((r) => r.json())
        .then((d) => {
          this.askText = JSON.stringify(d, null, 2);
        })
        .catch((e) => {
          this.askText = String(e);
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
</style>
