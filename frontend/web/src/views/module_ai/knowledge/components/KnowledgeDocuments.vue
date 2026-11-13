<template>
  <section class="knowledge-workspace" :aria-busy="busy">
    <header class="workspace-heading">
      <div>
        <span class="eyebrow">KNOWLEDGE DOCUMENTS</span>
        <h2>让回答有据可查</h2>
        <p>上传资料后提问，回答会附上所引用的文档片段。回答仅使用当前知识库内的资料。</p>
      </div>
    </header>

    <div class="workspace-columns">
      <section class="documents-panel" aria-labelledby="documents-title">
        <div class="section-heading">
          <h3 id="documents-title">
            文档 <span>{{ documents.length }} / 100</span>
          </h3>
          <ElButton :disabled="busy || loading" @click="loadDocuments">刷新</ElButton>
        </div>
        <ElButton
          v-if="canManage"
          type="primary"
          :loading="uploading"
          :disabled="busy || loading || loadFailed || documents.length >= 100"
          @click="fileInput?.click()"
          >上传文档</ElButton
        >
        <input
          ref="fileInput"
          type="file"
          accept=".txt,.md,.pdf"
          aria-label="上传知识库文档"
          hidden
          @change="uploadFile"
        />
        <p class="hint">
          TXT、Markdown、文字 PDF · 每份不超过 2 MB<br />PDF 最多 50 页，提取文字不超过 60 KB。
        </p>
        <ElAlert v-if="mutationError" :title="mutationError" type="error" :closable="false" />
        <p v-if="busy" role="status" class="hint">
          {{ asking ? "正在检索资料并生成回答…" : "正在处理文档，请稍候…" }}
        </p>
        <div v-if="loadFailed" class="empty-state" role="alert">
          <p>文档列表加载失败</p>
          <ElButton @click="loadDocuments">重试</ElButton>
        </div>
        <p v-else-if="loading" role="status" class="empty-state">正在加载文档…</p>
        <p v-else-if="!documents.length" class="empty-state">还没有资料，从上传第一份文档开始。</p>
        <ul v-else class="document-list">
          <li v-for="doc in documents" :key="doc.id" class="document-item">
            <div class="document-heading">
              <strong>{{ doc.name }}</strong>
              <ElTag :type="doc.needs_reindex ? 'warning' : 'success'" size="small">{{
                doc.needs_reindex ? "需要重建" : "可检索"
              }}</ElTag>
            </div>
            <p class="hint">
              {{ doc.chunk_count }} 个片段 · {{ new Date(doc.created_time).toLocaleString() }}
            </p>
            <div v-if="canManage" class="document-actions">
              <ElButton link type="primary" :disabled="busy" @click="reindex(doc)"
                >重建索引</ElButton
              >
              <ElButton link type="danger" :disabled="busy" @click="remove(doc)">删除</ElButton>
            </div>
          </li>
        </ul>
      </section>

      <section class="answer-panel" aria-labelledby="question-title">
        <div class="section-heading">
          <h3 id="question-title">基于资料提问</h3>
          <span class="eyebrow">RAG</span>
        </div>
        <p class="hint">
          向量模型由管理员统一配置。问答使用你的聊天模型配置；更换向量模型后，维护人需重建文档索引。
        </p>
        <ElInput
          v-model="question"
          type="textarea"
          :rows="4"
          maxlength="1000"
          show-word-limit
          aria-label="知识库问题"
          placeholder="例如：员工年假有哪些规定？"
          :disabled="busy"
        />
        <div class="question-actions">
          <span class="hint">{{ searchableCount }} 份文档可检索</span>
          <ElButton
            type="primary"
            :loading="asking"
            :disabled="busy || loading || loadFailed || !searchableCount || !question.trim()"
            @click="ask"
            >提问</ElButton
          >
        </div>
        <ElAlert
          v-if="askError"
          title="提问失败，请检查模型配置或稍后重试。"
          type="error"
          :closable="false"
        />
        <div v-if="answer" class="answer-result" aria-live="polite">
          <h3>回答</h3>
          <p class="answer-text">{{ answer.answer }}</p>
          <h3 v-if="answer.sources.length">引用来源</h3>
          <article v-for="source in answer.sources" :key="source.number" class="source-card">
            <h4>[{{ source.number }}] {{ source.name }}</h4>
            <p>{{ source.text }}</p>
          </article>
        </div>
        <div v-else-if="!asking && !askError" class="answer-placeholder">
          <span class="eyebrow">从资料到答案</span>
          <p>回答与引用将在这里展示。</p>
          <small>资料不足时会明确说明，请结合原文核对回答。</small>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElAlert, ElButton, ElInput, ElMessage, ElMessageBox, ElTag } from "element-plus";
import {
  KnowledgeAPI,
  type KnowledgeAnswer,
  type KnowledgeDocument,
} from "@/api/module_ai/knowledge";

const props = defineProps<{ baseId: string; canManage: boolean }>();
const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const loadFailed = ref(false);
const uploading = ref(false);
const mutating = ref(false);
const asking = ref(false);
const busy = computed(() => uploading.value || mutating.value || asking.value);
const searchableCount = computed(() => documents.value.filter((doc) => !doc.needs_reindex).length);
const fileInput = ref<HTMLInputElement>();
const question = ref("");
const answer = ref<KnowledgeAnswer | null>(null);
const askError = ref(false);
const mutationError = ref("");

async function loadDocuments() {
  loading.value = true;
  loadFailed.value = true;
  try {
    const response = await KnowledgeAPI.list(props.baseId);
    if (response.data.code === 0) {
      documents.value = response.data.data;
      loadFailed.value = false;
    }
  } catch {
    /* 请求层统一展示错误，保留重试入口。 */
  } finally {
    loading.value = false;
  }
}

async function uploadFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || busy.value || !props.canManage) return;
  if (!/\.(txt|md|pdf)$/i.test(file.name) || !file.size || file.size > 2 * 1024 * 1024) {
    ElMessage.warning("请选择不超过 2 MB 的非空 TXT、Markdown 或文字 PDF 文件");
    return;
  }
  uploading.value = true;
  answer.value = null;
  mutationError.value = "";
  try {
    const response = await KnowledgeAPI.upload(props.baseId, file);
    if (response.data.code !== 0) throw new Error("upload failed");
  } catch {
    mutationError.value = "上传未完成，请刷新文档列表确认结果后重试。";
  } finally {
    await loadDocuments();
    uploading.value = false;
  }
}

async function reindex(doc: KnowledgeDocument) {
  if (busy.value || !props.canManage) return;
  mutating.value = true;
  answer.value = null;
  mutationError.value = "";
  try {
    const response = await KnowledgeAPI.reindex(props.baseId, doc.id);
    if (response.data.code !== 0) throw new Error("reindex failed");
  } catch {
    mutationError.value = "重建未完成，请刷新文档列表确认结果后重试。";
  } finally {
    await loadDocuments();
    mutating.value = false;
  }
}

async function remove(doc: KnowledgeDocument) {
  if (busy.value || !props.canManage) return;
  try {
    await ElMessageBox.confirm(`删除「${doc.name}」及其索引？删除后需重新上传。`, "删除文档", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  if (busy.value || !props.canManage) return;
  mutating.value = true;
  answer.value = null;
  mutationError.value = "";
  try {
    const response = await KnowledgeAPI.remove(props.baseId, doc.id);
    if (response.data.code !== 0) throw new Error("delete failed");
  } catch {
    mutationError.value = "删除未完成，请刷新文档列表确认结果后重试。";
  } finally {
    await loadDocuments();
    mutating.value = false;
  }
}

async function ask() {
  const value = question.value.trim();
  if (
    !value ||
    value.length > 1000 ||
    busy.value ||
    loading.value ||
    loadFailed.value ||
    !searchableCount.value
  )
    return;
  asking.value = true;
  answer.value = null;
  askError.value = false;
  try {
    const response = await KnowledgeAPI.ask(props.baseId, value);
    if (response.data.code !== 0) throw new Error("ask failed");
    answer.value = response.data.data;
  } catch {
    askError.value = true;
  } finally {
    asking.value = false;
  }
}

onMounted(loadDocuments);
</script>

<style scoped lang="scss">
.knowledge-workspace {
  color: var(--el-text-color-primary);
}
.workspace-heading,
.section-heading,
.document-heading,
.question-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}
.workspace-heading {
  align-items: flex-start;
  margin-bottom: 28px;
}
.workspace-heading h2 {
  margin: 8px 0 12px;
  font-size: 26px;
  letter-spacing: -0.5px;
}
.workspace-heading p,
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.eyebrow {
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
}
.workspace-columns {
  display: grid;
  grid-template-columns: minmax(240px, 0.85fr) minmax(0, 1.4fr);
  gap: 28px;
}
.documents-panel {
  padding-right: 28px;
  border-right: 1px solid var(--el-border-color-lighter);
}
.section-heading {
  margin-bottom: 16px;
}
.section-heading h3,
.answer-result h3 {
  margin: 0;
  font-size: 16px;
}
.section-heading h3 span {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}
.document-list {
  padding: 0;
  margin: 20px 0 0;
  list-style: none;
}
.document-item {
  padding: 16px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}
.document-heading {
  align-items: flex-start;
}
.document-heading strong {
  overflow-wrap: anywhere;
  font-size: 14px;
}
.document-heading :deep(.el-tag) {
  flex-shrink: 0;
}
.document-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.question-actions {
  margin: 16px 0 24px;
}
.empty-state,
.answer-placeholder {
  padding: 40px 12px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.8;
}
.answer-placeholder {
  margin-top: 32px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.answer-text,
.source-card p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.9;
}
.answer-result {
  margin-top: 28px;
}
.source-card {
  padding: 16px;
  margin-top: 12px;
  background: var(--el-fill-color-light);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 4px;
}
.source-card h4 {
  margin: 0 0 8px;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.source-card p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
@media (width <= 760px) {
  .workspace-columns {
    grid-template-columns: 1fr;
  }
  .documents-panel {
    padding: 0 0 20px;
    border-right: 0;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
  .workspace-heading h2 {
    font-size: 22px;
  }
}
</style>
