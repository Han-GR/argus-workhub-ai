<template>
  <section class="knowledge-workspace" :aria-busy="mutating">
    <section class="documents-panel" aria-labelledby="documents-title">
      <div class="section-heading">
        <h3 id="documents-title">
          文档 <span>{{ documents.length }}</span>
        </h3>
        <div class="toolbar-actions">
          <ElButton :icon="Refresh" :disabled="mutating || loading" @click="loadDocuments"
            >刷新</ElButton
          >
          <ElButton type="primary" :icon="Upload" :disabled="mutating" @click="openUpload"
            >上传文档</ElButton
          >
        </div>
      </div>
      <ElTabs v-model="view" @tab-change="loadDocuments">
        <ElTabPane label="全部可见" name="all" />
        <ElTabPane label="全公司" name="company" />
        <ElTabPane label="本部门" name="department" />
        <ElTabPane label="我上传的" name="mine" />
      </ElTabs>
      <ElAlert v-if="mutationError" :title="mutationError" type="error" :closable="false" />
      <p v-if="mutating" role="status" class="hint">正在处理文档，请稍候…</p>
      <div v-if="loadFailed" class="empty-state" role="alert">
        <p>文档列表加载失败</p>
        <ElButton @click="loadDocuments">重试</ElButton>
      </div>
      <p v-else-if="loading" role="status" class="empty-state">正在加载文档…</p>
      <div v-else-if="!documents.length" class="empty-state">
        <div class="empty-icon"><FolderOpened aria-hidden="true" /></div>
        <h3>还没有可见的文档</h3>
        <p>把团队的经验和资料放在这里，让每一次提问都有据可查。</p>
        <ElButton type="primary" plain :disabled="mutating" @click="openUpload"
          >上传第一份文档</ElButton
        >
      </div>
      <ul v-else class="document-list">
        <li v-for="doc in documents" :key="doc.id" class="document-item">
          <div class="document-heading">
            <strong class="document-name"><Document aria-hidden="true" />{{ doc.name }}</strong>
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
      <footer class="panel-footer">
        <span>支持 TXT、Markdown、文字 PDF · 单份不超过 2 MB</span><span>仅上传者可编辑和删除</span>
      </footer>
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
        <p class="hint">
          支持 TXT、Markdown、文字 PDF，每份不超过 2 MB。PDF 最多 50 页，提取文字不超过 60 KB。
        </p>
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
import { Document, FolderOpened, Refresh, Upload } from "@element-plus/icons-vue";
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
.documents-panel {
  overflow: hidden;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
}
.section-heading {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px 12px;
}
.section-heading h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.section-heading h3 span {
  display: inline-block;
  min-width: 24px;
  padding: 2px 7px;
  margin-left: 8px;
  font-size: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.toolbar-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
:deep(.el-tabs__header) {
  padding: 0 28px;
  margin: 0;
}
:deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--el-border-color-lighter);
}
:deep(.el-tabs__item) {
  height: 50px;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.document-list {
  padding: 0 28px;
  margin: 0;
  list-style: none;
}
.document-item {
  position: relative;
  padding: 24px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.document-item:last-child {
  border-bottom: 0;
}
.document-heading {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}
.document-name {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 14px;
  font-weight: 600;
}
.document-name svg {
  flex: 0 0 20px;
  width: 20px;
  color: var(--el-color-primary);
}
.document-heading :deep(.el-tag) {
  flex-shrink: 0;
}
.document-item .hint {
  margin: 10px 0 0 32px;
}
.document-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}
.empty-state {
  padding: 64px 24px 72px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.empty-icon {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-radius: 20px;
}
.empty-icon svg {
  width: 34px;
  height: 34px;
}
.empty-state h3 {
  margin: 0 0 8px;
  color: var(--el-text-color-primary);
  font-size: 17px;
  font-weight: 600;
}
.empty-state p {
  margin: 0 0 24px;
}
.panel-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  justify-content: space-between;
  padding: 16px 28px;
  background: var(--el-fill-color-lighter);
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
@media (width <= 600px) {
  .section-heading {
    padding: 20px 16px 8px;
    flex-wrap: wrap;
  }
  :deep(.el-tabs__header) {
    padding: 0 16px;
  }
  .document-list {
    padding: 0 16px;
  }
  .document-heading {
    align-items: flex-start;
  }
  .panel-footer {
    padding: 16px;
  }
  .empty-state {
    padding: 44px 16px;
  }
}
</style>
