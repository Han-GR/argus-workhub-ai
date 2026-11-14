<template>
  <section class="knowledge-workspace" :aria-busy="mutating">
    <section class="documents-panel" aria-labelledby="documents-title">
      <div class="section-heading">
        <h3 id="documents-title">
          文档 <span>{{ documents.length }}</span>
        </h3>
        <ElButton :disabled="mutating || loading" @click="loadDocuments">刷新</ElButton>
      </div>
      <ElTabs v-model="view" @tab-change="loadDocuments">
        <ElTabPane label="全部可见" name="all" />
        <ElTabPane label="全公司" name="company" />
        <ElTabPane label="本部门" name="department" />
        <ElTabPane label="我上传的" name="mine" />
      </ElTabs>
      <ElButton type="primary" :disabled="mutating" @click="openUpload">上传文档</ElButton>
      <p class="hint">
        TXT、Markdown、文字 PDF · 每份不超过 2 MB<br />PDF 最多 50 页，提取文字不超过 60 KB。
      </p>
      <ElAlert v-if="mutationError" :title="mutationError" type="error" :closable="false" />
      <p v-if="mutating" role="status" class="hint">正在处理文档，请稍候…</p>
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
            <ElButton link type="primary" :disabled="mutating" @click="openEdit(doc)"
              >编辑</ElButton
            >
            <ElButton link type="primary" :disabled="mutating" @click="reindex(doc)"
              >重建索引</ElButton
            >
            <ElButton link type="danger" :disabled="mutating" @click="remove(doc)">删除</ElButton>
          </div>
        </li>
      </ul>
    </section>

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
import { onMounted, reactive, ref } from "vue";
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
  type KnowledgeDocument,
} from "@/api/module_ai/knowledge";
const props = defineProps<{ departmentName: string | null }>();
const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const loadFailed = ref(false);
const mutating = ref(false);
const view = ref<DocumentView>("all");
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
  if (!doc.can_edit || mutating.value) return;
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
  if (mutating.value || fileError.value || (editing.value ? !form.name.trim() : !form.file)) return;
  mutating.value = true;
  saveError.value = false;
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
  if (mutating.value || !doc.can_edit) return;
  mutating.value = true;
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
  if (mutating.value || !doc.can_edit) return;
  try {
    await ElMessageBox.confirm(`删除「${doc.name}」及其索引？删除后需重新上传。`, "删除文档", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  if (mutating.value) return;
  mutating.value = true;
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
onMounted(loadDocuments);
</script>
<style scoped lang="scss">
.knowledge-workspace {
  color: var(--el-text-color-primary);
}
.section-heading,
.document-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.section-heading {
  margin-bottom: 16px;
}
.section-heading h3 {
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
  padding: 20px 0;
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
.empty-state {
  padding: 40px 12px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.8;
}
</style>
