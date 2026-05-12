<template>
  <div class="wrap">
    <h1>ai-05-knowledge · RAG</h1>
    <p class="hint">界面模式：深色单栏（与默认沙箱一致）</p>

    <section class="card">
      <h2>健康检查</h2>
      <pre class="pre">{{ healthText }}</pre>
    </section>

    <section class="card">
      <h2>入库</h2>
      <input type="file" accept=".pdf,.html,.htm,.md,.markdown" @change="onFile" />
      <button class="btn" :disabled="ingesting" @click="ingest">上传并入库</button>
      <pre class="pre">{{ ingestText }}</pre>
    </section>

    <section class="card">
      <h2>问答</h2>
      <textarea v-model="question" rows="3" class="ta" placeholder="输入问题" />
      <button class="btn" :disabled="asking" @click="ask">提问</button>
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
      file: null,
      ingestText: '',
      ingesting: false,
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
  },
  methods: {
    onFile(ev) {
      const f = ev.target.files && ev.target.files[0];
      this.file = f || null;
    },
    ingest() {
      if (!this.file) {
        this.ingestText = '请先选择文件';
        return;
      }
      this.ingesting = true;
      this.ingestText = '上传中…';
      const fd = new FormData();
      fd.append('file', this.file);
      fd.append('title', this.file.name);
      fetch('/api/v1/rag/ingest', { method: 'POST', body: fd })
        .then((r) => r.json())
        .then((d) => {
          this.ingestText = JSON.stringify(d, null, 2);
        })
        .catch((e) => {
          this.ingestText = String(e);
        })
        .finally(() => {
          this.ingesting = false;
        });
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
  max-width: 720px;
  margin: 0 auto;
  padding: 24px;
}
.hint {
  color: #9aa3c7;
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
.ta {
  width: 100%;
  margin: 8px 0;
  background: #151a2e;
  color: #e8ecff;
  border: 1px solid #2a3152;
  border-radius: 8px;
  padding: 8px;
}
</style>
