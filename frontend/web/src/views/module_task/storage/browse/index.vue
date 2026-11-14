<template>
  <div class="archive-page" :aria-busy="busy">
    <header class="archive-heading">
      <div>
        <span class="eyebrow">团队档案 / 文件</span>
        <h1>文件管理</h1>
        <p>有序保存团队资料，让每一份文件在合适的范围内共享。</p>
      </div>
      <ElSelect
        v-model="sourceId"
        aria-label="档案存储源"
        placeholder="选择存储源"
        :disabled="busy"
        class="source-select"
        @change="changeSource"
      >
        <ElOption
          v-for="source in sources"
          :key="source.id"
          :label="source.name"
          :value="source.id"
        />
      </ElSelect>
    </header>
    <ElAlert v-if="sourceError" title="存储源加载失败，请重试" type="error" :closable="false" />
    <section class="archive-panel">
      <div class="archive-toolbar">
        <div class="archive-path">
          <ElButton text :disabled="busy || !directory" @click="goUp">上一级</ElButton>
          <ElBreadcrumb separator="/">
            <ElBreadcrumbItem
              ><button class="path-link" :disabled="busy" @click="navigate('')">
                全部文件
              </button></ElBreadcrumbItem
            >
            <ElBreadcrumbItem v-for="(part, index) in pathParts" :key="index"
              ><button
                class="path-link"
                :disabled="busy"
                @click="navigate(pathParts.slice(0, index + 1).join('/'))"
              >
                {{ part }}
              </button></ElBreadcrumbItem
            >
          </ElBreadcrumb>
        </div>
        <div class="toolbar-buttons">
          <ElButton :disabled="busy" @click="refresh">刷新</ElButton>
          <ElButton
            v-hasPerm="['module_task:storage:browse:update']"
            :disabled="busy || !sourceId"
            @click="createDirectory"
            >新建文件夹</ElButton
          >
          <ElButton
            v-hasPerm="['module_task:storage:browse:upload']"
            type="primary"
            :icon="Upload"
            :disabled="busy || !sourceId"
            @click="fileInput?.click()"
            >上传文件</ElButton
          >
        </div>
      </div>
      <div class="archive-filters">
        <span v-if="directory" class="scope-hint"><Lock />新文件继承顶层文件夹的共享范围</span>
        <div v-else class="upload-scope">
          <span>新建 / 上传范围</span
          ><ElSelect v-model="visibility" aria-label="上传文件可见范围" :disabled="busy"
            ><ElOption
              v-for="scope in scopes"
              :key="scope.value"
              :label="scope.label"
              :value="scope.value"
          /></ElSelect>
        </div>
        <ElInput
          v-model="keyword"
          placeholder="搜索当前文件夹"
          aria-label="搜索文件名称"
          clearable
          :prefix-icon="Search"
          class="file-search"
        />
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <ArgusTable
        :loading="loading"
        :data="filteredEntries"
        :columns="columns"
        empty-text="当前范围暂无文件，可以上传资料或新建文件夹。"
      >
        <template #name="{ row }"
          ><button
            class="file-name"
            :class="{ folder: row.is_dir }"
            :disabled="busy"
            @click="row.is_dir ? navigate(row.key) : preview(row)"
          >
            <ElIcon><Folder v-if="row.is_dir" /><Document v-else /></ElIcon
            ><span>{{ row.name }}</span>
          </button></template
        >
        <template #visibility="{ row }"
          ><ElTag
            size="small"
            effect="plain"
            :type="
              row.visibility === 'company'
                ? 'success'
                : row.visibility === 'department'
                  ? 'primary'
                  : 'info'
            "
            >{{ scopeLabel(row.visibility) }}</ElTag
          ><span v-if="row.inherited" class="inherited">继承</span></template
        >
        <template #owner="{ row }">{{
          row.owner_name || (row.owner_id === userStore.info.id ? "我" : "原上传者")
        }}</template>
        <template #size="{ row }">{{ row.is_dir ? "—" : formatSize(row.size) }}</template>
        <template #modified_time="{ row }">{{
          new Date(row.modified_time).toLocaleString()
        }}</template>
        <template #operation="{ row }">
          <div class="file-actions">
            <ElButton
              v-hasPerm="['module_task:storage:browse:download']"
              link
              type="primary"
              :disabled="busy"
              @click="download(row)"
              >下载</ElButton
            >
            <ElDropdown
              trigger="click"
              :disabled="busy"
              @command="(command: string) => action(command, row)"
            >
              <ElButton link type="primary" :disabled="busy" aria-label="文件操作"
                >更多<ElIcon><ArrowDown /></ElIcon
              ></ElButton>
              <template #dropdown
                ><ElDropdownMenu>
                  <ElDropdownItem
                    v-if="!row.is_dir"
                    v-hasPerm="['module_task:storage:browse:update']"
                    command="copy"
                    >复制到</ElDropdownItem
                  >
                  <template v-if="row.can_manage">
                    <ElDropdownItem
                      v-hasPerm="['module_task:storage:browse:update']"
                      command="rename"
                      >重命名</ElDropdownItem
                    >
                    <ElDropdownItem v-hasPerm="['module_task:storage:browse:update']" command="move"
                      >移动到</ElDropdownItem
                    >
                    <ElDropdownItem
                      v-if="!row.inherited"
                      v-hasPerm="['module_task:storage:browse:update']"
                      command="visibility"
                      >共享范围</ElDropdownItem
                    >
                    <ElDropdownItem
                      v-hasPerm="['module_task:storage:browse:delete']"
                      command="delete"
                      divided
                      >删除</ElDropdownItem
                    >
                  </template>
                </ElDropdownMenu></template
              >
            </ElDropdown>
          </div>
        </template>
      </ArgusTable>
      <footer class="archive-footer">
        <span>{{ filteredEntries.length }} 项 · 仅显示你有权访问的文件</span
        ><span>文件夹内的资料统一继承共享范围</span>
      </footer>
    </section>
    <ElDialog
      v-model="previewVisible"
      :title="previewFile?.name || '文件预览'"
      top="6vh"
      width="min(1040px, 95vw)"
    >
      <div v-loading="previewLoading" class="preview-body" aria-live="polite">
        <p v-if="previewError" class="preview-hint" role="alert">{{ previewError }}</p>
        <img
          v-else-if="previewKind === 'image' && previewUrl"
          :src="previewUrl"
          :alt="previewFile?.name"
          class="preview-image"
          @error="previewError = '图片无法预览，请下载后查看。'"
        />
        <object
          v-else-if="previewKind === 'pdf' && previewUrl"
          :data="previewUrl"
          type="application/pdf"
          class="preview-pdf"
          aria-label="PDF 文件预览"
        >
          <p>浏览器无法显示 PDF，请下载后查看。</p>
        </object>
        <pre v-else-if="previewKind === 'text' && !previewLoading" class="preview-text">{{
          previewText
        }}</pre>
        <p v-else-if="!previewLoading" class="preview-hint">
          暂不支持此格式在线预览，请下载后查看。
        </p>
      </div>
      <template #footer
        ><ElButton @click="previewVisible = false">关闭</ElButton
        ><ElButton
          v-if="previewFile"
          v-hasPerm="['module_task:storage:browse:download']"
          type="primary"
          :disabled="busy"
          @click="download(previewFile, previewSourceId)"
          >下载文件</ElButton
        ></template
      >
    </ElDialog>
    <input
      ref="fileInput"
      type="file"
      hidden
      multiple
      aria-label="选择档案文件"
      @change="uploadFiles"
    />
    <ElDialog
      v-model="editorVisible"
      :title="
        editingAction === 'visibility'
          ? '共享范围'
          : editingAction === 'copy'
            ? '复制文件'
            : '移动文件'
      "
      width="min(480px, 95vw)"
      :close-on-click-modal="!busy"
      :close-on-press-escape="!busy"
      :show-close="!busy"
    >
      <ElForm label-position="top">
        <template v-if="editingAction !== 'visibility'">
          <ElFormItem label="目标存储源"
            ><ElSelect
              v-model="targetSourceId"
              :disabled="busy || !!selected?.is_dir"
              class="full-width"
              ><ElOption
                v-for="source in sources"
                :key="source.id"
                :label="source.name"
                :value="source.id" /></ElSelect
          ></ElFormItem>
          <ElFormItem label="目标完整路径"
            ><ElInput
              v-model="targetPath"
              :disabled="busy"
              placeholder="例如：部门资料/项目说明.pdf"
          /></ElFormItem>
          <p class="dialog-hint">移入文件夹后，将继承目标文件夹的共享范围；不会覆盖已有文件。</p>
        </template>
        <ElFormItem v-else label="可见范围"
          ><ElSelect v-model="targetVisibility" :disabled="busy" class="full-width"
            ><ElOption
              v-for="scope in scopes"
              :key="scope.value"
              :label="scope.label"
              :value="scope.value" /></ElSelect
        ></ElFormItem>
        <p v-if="editingAction === 'visibility'" class="dialog-hint">
          文件夹修改后，所有内部文件同步生效；包含他人上传文件时，需要相应的部门管理权限。
        </p>
      </ElForm>
      <template #footer
        ><ElButton :disabled="busy" @click="editorVisible = false">取消</ElButton
        ><ElButton
          type="primary"
          :loading="busy"
          :disabled="editingAction !== 'visibility' && !targetPath.trim()"
          @click="saveOperation"
          >确定</ElButton
        ></template
      >
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowDown, Document, Folder, Lock, Search, Upload } from "@element-plus/icons-vue";
import { saveAs } from "file-saver";
import { useUserStore } from "@stores";
import StorageAPI, {
  type ArchiveSource,
  type ArchiveVisibility,
  type StorageObject,
} from "@/api/module_storage/browse";
import ArgusTable from "@/components/tables/argus-table/index.vue";
import type { ColumnOption } from "@/types/component";

defineOptions({ name: "WorkflowBrowse" });
const userStore = useUserStore();
const scopes = [
  { value: "private", label: "仅自己可见" },
  { value: "department", label: "仅部门可见" },
  { value: "company", label: "全公司可见" },
];
const scopesLabel = Object.fromEntries(scopes.map((s) => [s.value, s.label]));
const scopeLabel = (value: string) => scopesLabel[value] || value;
const sources = ref<ArchiveSource[]>([]);
const sourceId = ref<number>();
const sourceError = ref(false);
const directory = ref("");
const keyword = ref("");
const entries = ref<StorageObject[]>([]);
const visibility = ref<ArchiveVisibility>("private");
const loading = ref(false);
const busy = ref(false);
const error = ref("");
const fileInput = ref<HTMLInputElement>();
const pathParts = computed(() => directory.value.split("/").filter(Boolean));
const filteredEntries = computed(() =>
  entries.value.filter((e) => e.name?.toLowerCase().includes(keyword.value.trim().toLowerCase()))
);
const columns: ColumnOption[] = [
  { prop: "name", label: "文件名称", minWidth: 220, useSlot: true, slotName: "name" },
  { prop: "visibility", label: "可见范围", width: 160, useSlot: true, slotName: "visibility" },
  { prop: "owner", label: "上传者", width: 110, useSlot: true, slotName: "owner" },
  { prop: "size", label: "大小", width: 100, useSlot: true, slotName: "size" },
  {
    prop: "modified_time",
    label: "创建时间",
    minWidth: 170,
    useSlot: true,
    slotName: "modified_time",
  },
  {
    prop: "operation",
    label: "操作",
    width: 170,
    useSlot: true,
    slotName: "operation",
    fixed: "right",
  },
];
let generation = 0;
async function load() {
  const current = ++generation;
  entries.value = [];
  error.value = "";
  if (!sourceId.value) return;
  loading.value = true;
  try {
    const result = await StorageAPI.listFiles({
      source_id: sourceId.value,
      prefix: directory.value,
    });
    if (result.data.code !== 0) throw new Error("list failed");
    if (current === generation)
      entries.value = Array.isArray(result.data.data) ? result.data.data : result.data.data.items;
  } catch {
    if (current === generation) error.value = "文件加载失败，请刷新重试或返回上一级。";
  } finally {
    if (current === generation) loading.value = false;
  }
}
async function loadSources() {
  sourceError.value = false;
  try {
    const response = await StorageAPI.sources();
    if (response.data.code !== 0) throw new Error("sources failed");
    sources.value = response.data.data;
    if (!sources.value.some((s) => s.id === sourceId.value))
      sourceId.value = (sources.value.find((s) => s.is_default) || sources.value[0])?.id;
  } catch {
    sourceError.value = true;
  }
}
async function refresh() {
  await loadSources();
  await load();
}
function navigate(path: string) {
  if (busy.value) return;
  directory.value = path;
  keyword.value = "";
  void load();
}
function goUp() {
  navigate(pathParts.value.slice(0, -1).join("/"));
}
function changeSource() {
  navigate("");
}
const pathBody = (row: StorageObject) => ({ source_id: sourceId.value, remote_path: row.key! });
async function checked(request: Promise<{ data: { code: number } }>) {
  const response = await request;
  if (response.data.code !== 0) throw new Error("operation failed");
}
async function run(operation: () => Promise<unknown>) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await operation();
    await load();
  } catch {
    error.value = "操作未完成，请刷新确认后重试。";
  } finally {
    busy.value = false;
  }
}
async function uploadFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  if (!sourceId.value || !files.length) return;
  await run(async () => {
    for (const file of files) {
      const data = new FormData();
      data.append("file", file);
      data.append("source_id", String(sourceId.value));
      data.append("remote_path", directory.value ? `${directory.value}/` : file.name);
      data.append("visibility", visibility.value);
      await checked(StorageAPI.uploadFile(data));
    }
    ElMessage.success("上传完成");
  });
}
async function createDirectory() {
  const result = await ElMessageBox.prompt(
    "请输入文件夹名称，内部文件将继承其共享范围",
    "新建文件夹",
    { inputPattern: /^[^/\\\\]+$/, inputErrorMessage: "请输入不含斜杠的名称" }
  ).catch(() => null);
  if (!result) return;
  await run(() =>
    checked(
      StorageAPI.mkdir({
        source_id: sourceId.value,
        remote_dir: directory.value ? `${directory.value}/${result.value}` : result.value,
        visibility: visibility.value,
      })
    )
  );
}
async function download(row: StorageObject, downloadSourceId = sourceId.value) {
  await run(async () => {
    const body = { source_id: downloadSourceId, remote_path: row.key! };
    const response = row.is_dir
      ? await StorageAPI.downloadDir(body)
      : await StorageAPI.downloadFile(body);
    saveAs(response.data, row.is_dir ? `${row.name}.zip` : row.name);
  });
}
const previewVisible = ref(false);
const previewLoading = ref(false);
const previewFile = ref<StorageObject>();
const previewSourceId = ref<number>();
const previewKind = ref("");
const previewUrl = ref("");
const previewText = ref("");
const previewError = ref("");
let previewGeneration = 0;
function clearPreview() {
  previewGeneration += 1;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = "";
  previewText.value = "";
  previewLoading.value = false;
}
async function preview(row: StorageObject) {
  clearPreview();
  const current = previewGeneration;
  previewFile.value = row;
  previewSourceId.value = sourceId.value;
  previewError.value = "";
  const extension = row.name?.split(".").pop()?.toLowerCase() || "";
  const imageTypes: Record<string, string> = {
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    gif: "image/gif",
    webp: "image/webp",
    avif: "image/avif",
    bmp: "image/bmp",
  };
  previewKind.value = imageTypes[extension]
    ? "image"
    : extension === "pdf"
      ? "pdf"
      : ["txt", "md", "csv", "json", "log"].includes(extension)
        ? "text"
        : "";
  previewVisible.value = true;
  if (!previewKind.value) return;
  const limit = previewKind.value === "text" ? 1024 * 1024 : 20 * 1024 * 1024;
  if ((row.size || 0) > limit) {
    previewError.value = "文件较大，请下载后查看。文本预览上限 1 MB，图片和 PDF 上限 20 MB。";
    return;
  }
  previewLoading.value = true;
  try {
    const response = await StorageAPI.downloadFile({
      source_id: previewSourceId.value,
      remote_path: row.key!,
    });
    if (current !== previewGeneration) return;
    if (response.data.size > limit) {
      previewError.value = "文件较大，请下载后查看。";
      return;
    }
    if (previewKind.value === "text") {
      const text = await response.data.text();
      if (current === previewGeneration) previewText.value = text;
    } else
      previewUrl.value = URL.createObjectURL(
        new Blob([response.data], { type: imageTypes[extension] || "application/pdf" })
      );
  } catch {
    if (current === previewGeneration)
      previewError.value = "预览加载失败，请检查访问权限或稍后重试。";
  } finally {
    if (current === previewGeneration) previewLoading.value = false;
  }
}
watch(previewVisible, (visible) => {
  if (!visible) clearPreview();
});
onBeforeUnmount(clearPreview);
onDeactivated(() => {
  previewVisible.value = false;
  clearPreview();
});
const editorVisible = ref(false);
const selected = ref<StorageObject>();
const editingAction = ref("copy");
const targetPath = ref("");
const targetSourceId = ref<number>();
const targetVisibility = ref<ArchiveVisibility>("private");
async function action(command: string, row: StorageObject) {
  if (busy.value) return;
  if (command === "delete") {
    const confirmed = await ElMessageBox.confirm(
      `删除「${row.name}」${row.is_dir ? "及其全部内容" : ""}？此操作不可撤销。`,
      "删除档案",
      { type: "warning" }
    )
      .then(() => true)
      .catch(() => false);
    if (confirmed) await run(() => checked(StorageAPI.deleteFile(pathBody(row))));
  } else if (command === "rename") {
    const result = await ElMessageBox.prompt("请输入新名称", "重命名", {
      inputValue: row.name,
      inputPattern: /^[^/\\\\]+$/,
      inputErrorMessage: "请输入不含斜杠的名称",
    }).catch(() => null);
    if (result)
      await run(() =>
        checked(
          StorageAPI.renameFile({
            source_id: sourceId.value,
            source_path: row.key!,
            target_path: directory.value ? `${directory.value}/${result.value}` : result.value,
          })
        )
      );
  } else {
    selected.value = row;
    editingAction.value = command;
    targetPath.value = row.key || "";
    targetSourceId.value = sourceId.value;
    targetVisibility.value = row.visibility || "private";
    editorVisible.value = true;
  }
}
async function saveOperation() {
  if (!selected.value) return;
  await run(async () => {
    if (editingAction.value === "visibility")
      await checked(
        StorageAPI.setVisibility({
          ...pathBody(selected.value!),
          visibility: targetVisibility.value,
        })
      );
    else
      await checked(
        StorageAPI.copyFile({
          source_id: sourceId.value,
          source_path: selected.value!.key!,
          target_id: targetSourceId.value!,
          target_path: targetPath.value.trim(),
          move: editingAction.value === "move",
        })
      );
    editorVisible.value = false;
    ElMessage.success("操作完成");
  });
}
function formatSize(size = 0) {
  return size < 1024
    ? `${size} B`
    : size < 1024 * 1024
      ? `${(size / 1024).toFixed(1)} KB`
      : `${(size / 1024 / 1024).toFixed(1)} MB`;
}
onMounted(refresh);
onActivated(() => {
  if (sources.value.length) void load();
});
</script>
<style scoped lang="scss">
.archive-page {
  max-width: 1480px;
  padding: 28px;
  margin: 0 auto;
  color: var(--el-text-color-primary);
}
.archive-heading,
.archive-toolbar,
.archive-filters,
.archive-footer {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}
.archive-heading {
  margin-bottom: 28px;
}
.eyebrow {
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
}
.archive-heading h1 {
  margin: 8px 0;
  font-size: 26px;
}
.archive-heading p,
.dialog-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.source-select {
  width: 220px;
}
.archive-panel {
  overflow: hidden;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
}
.archive-toolbar {
  padding: 20px 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.archive-path,
.toolbar-buttons,
.upload-scope,
.scope-hint {
  display: flex;
  gap: 12px;
  align-items: center;
}
.archive-path {
  min-width: 0;
  overflow: auto;
}
.path-link {
  padding: 0;
  color: inherit;
  font: inherit;
  cursor: pointer;
  background: transparent;
  border: 0;
  white-space: nowrap;
}
.toolbar-buttons {
  flex-wrap: wrap;
}
.toolbar-buttons :deep(.el-button + .el-button) {
  margin-left: 0;
}
.archive-filters {
  padding: 20px 24px;
}
.upload-scope {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.upload-scope :deep(.el-select) {
  width: 150px;
}
.file-search {
  width: 240px;
}
.scope-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.scope-hint svg {
  width: 14px;
}
.file-name {
  display: flex;
  gap: 10px;
  align-items: center;
  max-width: 100%;
  padding: 4px 0;
  color: var(--el-text-color-primary);
  font: inherit;
  background: none;
  border: 0;
}
.file-name span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-name .el-icon {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
}
.file-name {
  cursor: pointer;
}
.file-name:hover span {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.file-name:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 3px;
}
.file-name.folder .el-icon {
  color: var(--el-color-warning);
}
.inherited {
  margin-left: 6px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
}
.archive-footer {
  padding: 16px 24px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.full-width {
  width: 100%;
}
.file-actions {
  display: inline-flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 16px;
  white-space: nowrap;
}
.file-actions :deep(.el-button) {
  width: auto;
  min-width: 0;
  height: 28px;
  padding: 0;
  margin: 0;
}
.file-actions :deep(.el-dropdown) {
  display: inline-flex;
  align-items: center;
}
.preview-body {
  min-height: 260px;
  max-height: 70vh;
  overflow: auto;
  text-align: center;
}
.preview-image {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  margin: 0 auto;
  object-fit: contain;
}
.preview-pdf {
  display: block;
  width: 100%;
  height: 68vh;
  border: 0;
}
.preview-text {
  margin: 0;
  padding: 20px;
  font: 13px/1.8 monospace;
  text-align: left;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}
.preview-hint {
  padding: 64px 20px;
  color: var(--el-text-color-secondary);
  line-height: 1.8;
}
@media (width <= 600px) {
  .archive-page {
    padding: 12px;
  }
  .archive-toolbar,
  .archive-filters,
  .archive-footer {
    padding: 16px;
  }
  .file-search,
  .source-select {
    width: 100%;
  }
}
</style>
