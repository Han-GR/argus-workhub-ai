<template>
  <section class="knowledge-workspace" :aria-busy="busy">
    <header class="workspace-heading">
      <div>
        <span class="eyebrow">KNOWLEDGE DOCUMENTS</span>
        <h2>让回答有据可查</h2>
        <p>
          上传资料后提问，回答会附上所引用的文档片段。问答仅使用全公司共享及当前部门可见的资料。
        </p>
      </div>
    </header>

    <div class="workspace-columns">
      <section class="documents-panel" aria-labelledby="documents-title">
        <div class="section-heading">
          <h3 id="documents-title">
            文档 <span>{{ documents.length }}</span>
          </h3>
          <ElButton :disabled="busy || loading" @click="loadDocuments">刷新</ElButton>
        </div>
        <ElTabs v-model="view" @tab-change="loadDocuments">
          <ElTabPane label="全部可见" name="all" />
          <ElTabPane label="全公司" name="company" />
          <ElTabPane label="本部门" name="department" />
          <ElTabPane label="我上传的" name="mine" />
        </ElTabs>
        <ElButton type="primary" :disabled="busy" @click="openUpload">上传文档</ElButton>
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
        <p v-else-if="!documents.length" class="empty-state">
          此范围暂无文档，你可以上传资料并选择共享范围。
        </p>
        <ul v-else class="document-list">
          <li v-for="doc in documents" :key="doc.id" class="document-item">
            <div class="document-heading">
              <strong>{{ doc.name }}</strong>
              <ElTag :type="doc.needs_reindex ? 'warning' : 'success'" size="small">{{
                doc.needs_reindex ? "需要重建" : doc.can_query ? "可检索" : "不在当前问答范围"
              }}</ElTag>
            </div>
            <p class="hint">
              {{ doc.visibility === "company" ? "全公司可见" : `${doc.dept_name || "原部门"}可见` }}
              · {{ doc.uploader_name || "原上传者" }}上传<br />
              {{ doc.chunk_count }} 个片段 · {{ new Date(doc.created_time).toLocaleString() }}
            </p>
            <div v-if="doc.can_edit" class="document-actions">
              <ElButton link type="primary" :disabled="busy" @click="openEdit(doc)">编辑</ElButton>
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
          问答仅检索全公司和你当前部门的资料，与左侧列表筛选无关。聊天模型使用你的个人配置；索引失效的文档需由上传者重建。
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
          <span class="hint">按当前账号权限检索</span>
          <ElButton
            type="primary"
            :loading="asking"
            :disabled="busy || !question.trim()"
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
    <ElDialog
      v-model="editorVisible"
      :title="editing ? '编辑文档' : '上传文档'"
      width="min(520px, 95vw)"
      append-to-body
      :close-on-click-modal="!mutating"
      :close-on-press-escape="!mutating"
      :show-close="!mutating"
    >
      <ElForm label-position="top">
        <ElFormItem v-if="editing" label="文档名称"
          ><ElInput v-model="form.name" maxlength="200" aria-label="文档名称" :disabled="mutating"
        /></ElFormItem>
        <ElFormItem label="可见范围">
          <ElSelect v-model="form.visibility" aria-label="文档可见范围" :disabled="mutating">
            <ElOption value="company" label="全公司可见" />
            <ElOption
              value="department"
              label="仅部门可见"
              :disabled="!departmentName && editing?.visibility !== 'department'"
            />
          </ElSelect>
        </ElFormItem>
        <p class="hint">
          {{
            form.visibility === "company"
              ? "所有成员都可以查看，并将此文档用于问答。"
              : `仅${editing?.visibility === "department" ? editing.dept_name || "原部门" : departmentName || "当前部门"}成员可以将此文档用于问答。`
          }}
        </p>
        <ElFormItem :label="editing ? '替换文件（不选则保留原文）' : '选择文件'">
          <input
            :key="fileInputVersion"
            type="file"
            accept=".txt,.md,.pdf"
            aria-label="知识库文档文件"
            :disabled="mutating"
            @change="selectFile"
          />
        </ElFormItem>
        <ElAlert v-if="fileError" :title="fileError" type="error" :closable="false" />
        <ElAlert
          v-if="saveError"
          title="保存未完成，请刷新文档列表确认结果后重试。"
          type="error"
          :closable="false"
        />
      </ElForm>
      <template #footer>
        <ElButton :disabled="mutating" @click="editorVisible = false">取消</ElButton>
        <ElButton
          type="primary"
          :loading="mutating"
          :disabled="!!fileError || (editing ? !form.name.trim() : !form.file)"
          @click="submitDocument"
          >{{ editing ? "保存" : "上传" }}</ElButton
        >
      </template>
    </ElDialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTabPane,
  ElTabs,
  ElTag,
} from "element-plus";
import {
  KnowledgeAPI,
  type DocumentView,
  type DocumentVisibility,
  type KnowledgeAnswer,
  type KnowledgeDocument,
} from "@/api/module_ai/knowledge";
const props = defineProps<{ departmentName: string | null }>();
const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const loadFailed = ref(false);
const mutating = ref(false);
const asking = ref(false);
const busy = computed(() => mutating.value || asking.value);
const view = ref<DocumentView>("all");
const question = ref("");
const answer = ref<KnowledgeAnswer | null>(null);
const askError = ref(false);
const mutationError = ref("");
const editorVisible = ref(false);
const editing = ref<KnowledgeDocument | null>(null);
const form = reactive<{ name: string; visibility: DocumentVisibility; file?: File }>({
  name: "",
  visibility: "company",
});
const fileError = ref("");
const saveError = ref(false);
const fileInputVersion = ref(0);
let loadVersion = 0;
async function loadDocuments() {
  const current = ++loadVersion;
  loading.value = true;
  loadFailed.value = true;
  answer.value = null;
  try {
    const response = await KnowledgeAPI.list(view.value);
    if (current === loadVersion && response.data.code === 0) {
      documents.value = response.data.data;
      loadFailed.value = false;
    }
  } catch {
    /* 请求层统一展示错误。 */
  } finally {
    if (current === loadVersion) loading.value = false;
  }
}
function openUpload() {
  editing.value = null;
  Object.assign(form, {
    name: "",
    visibility: props.departmentName ? "department" : "company",
    file: undefined,
  });
  fileError.value = "";
  saveError.value = false;
  fileInputVersion.value += 1;
  editorVisible.value = true;
}
function openEdit(doc: KnowledgeDocument) {
  if (!doc.can_edit || busy.value) return;
  editing.value = doc;
  Object.assign(form, { name: doc.name, visibility: doc.visibility, file: undefined });
  fileError.value = "";
  saveError.value = false;
  fileInputVersion.value += 1;
  editorVisible.value = true;
}
function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  form.file = undefined;
  fileError.value = "";
  if (!file) return;
  if (!/\.(txt|md|pdf)$/i.test(file.name) || !file.size || file.size > 2 * 1024 * 1024) {
    fileError.value = "请选择不超过 2 MB 的非空 TXT、Markdown 或文字 PDF 文件";
    input.value = "";
    return;
  }
  form.file = file;
}
async function submitDocument() {
  if (busy.value || fileError.value || (editing.value ? !form.name.trim() : !form.file)) return;
  mutating.value = true;
  saveError.value = false;
  answer.value = null;
  try {
    const response = editing.value
      ? await KnowledgeAPI.update(editing.value.id, form.name.trim(), form.visibility, form.file)
      : await KnowledgeAPI.upload(form.file!, form.visibility);
    if (response.data.code !== 0) throw new Error("save failed");
    editorVisible.value = false;
  } catch {
    saveError.value = true;
  } finally {
    await loadDocuments();
    mutating.value = false;
  }
}
async function reindex(doc: KnowledgeDocument) {
  if (busy.value || !doc.can_edit) return;
  mutating.value = true;
  answer.value = null;
  mutationError.value = "";
  try {
    const response = await KnowledgeAPI.reindex(doc.id);
    if (response.data.code !== 0) throw new Error("reindex failed");
  } catch {
    mutationError.value = "重建未完成，请刷新文档列表确认结果后重试。";
  } finally {
    await loadDocuments();
    mutating.value = false;
  }
}
async function remove(doc: KnowledgeDocument) {
  if (busy.value || !doc.can_edit) return;
  try {
    await ElMessageBox.confirm(`删除「${doc.name}」及其索引？删除后需重新上传。`, "删除文档", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  if (busy.value) return;
  mutating.value = true;
  answer.value = null;
  mutationError.value = "";
  try {
    const response = await KnowledgeAPI.remove(doc.id);
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
  if (!value || value.length > 1000 || busy.value) return;
  asking.value = true;
  answer.value = null;
  askError.value = false;
  try {
    const response = await KnowledgeAPI.ask(value);
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
