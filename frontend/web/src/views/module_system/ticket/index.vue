<template>
  <div class="task-page">
    <header class="task-header">
      <div>
        <h2>我的任务</h2>
        <p>明确负责人和交付时间，一起推进团队工作。</p>
      </div>
      <div class="flex flex-wrap gap-2 justify-end">
        <ElButton v-hasPerm="['module_system:ticket:create']" type="primary" @click="openEditor()">
          <ArgusSvgIcon icon="ri:add-line" class="mr-1" />新建任务
        </ElButton>
      </div>
    </header>

    <ElCard shadow="never" class="mb-4">
      <div class="task-filters">
        <ElRadioGroup v-model="view" @change="resetPage">
          <ElRadioButton value="all">全部可见</ElRadioButton>
          <ElRadioButton value="assigned">我负责的</ElRadioButton>
          <ElRadioButton value="created">我创建的</ElRadioButton>
        </ElRadioGroup>
        <ElInput
          v-model="filters.title"
          placeholder="搜索任务标题"
          clearable
          class="task-search"
          @keyup.enter="resetPage"
          @clear="resetPage"
        />
        <ElSelect
          v-model="filters.status"
          placeholder="全部状态"
          clearable
          class="task-select"
          @change="resetPage"
        >
          <ElOption v-for="(label, i) in statuses" :key="i" :label="label" :value="i" />
        </ElSelect>
        <ElSelect
          v-model="filters.priority"
          placeholder="全部优先级"
          clearable
          class="task-select"
          @change="resetPage"
        >
          <ElOption v-for="(label, i) in priorities" :key="i" :label="label" :value="i" />
        </ElSelect>
        <ElButton :loading="loading" @click="resetPage">查询</ElButton>
      </div>
    </ElCard>

    <div class="task-list-caption">
      共 {{ total }} 项任务<span>仅显示你有权限访问的团队任务</span>
    </div>
    <ArgusCardGrid
      :items="tasks"
      :loading="loading"
      :pagination="{ current: pageNo, size: pageSize, total }"
      :lg="8"
      :xl="8"
      :md="12"
      :sm="12"
      header-class="task-card-header"
      @pagination:current-change="changePage"
      @pagination:size-change="changeSize"
    >
      <template #empty>
        <ArgusEmptyState
          icon="ri:task-line"
          title="暂无任务"
          description="创建一项任务，明确目标、负责人和交付时间。"
        />
      </template>
      <template #header="{ item }">
        <button type="button" class="task-title" @click="openDetail(item.id!)">
          {{ item.title }}
        </button>
        <ElTag :type="statusType(item.status)" size="small">{{ statuses[item.status ?? 0] }}</ElTag>
      </template>
      <template #default="{ item }">
        <div class="task-summary">
          {{ plainText(item.ticket_content || item.summary || "") || "暂无详细描述" }}
        </div>
        <div class="task-meta">
          <span>负责人</span><strong>{{ item.assigned_by?.name || "待分配" }}</strong>
        </div>
        <div class="task-meta">
          <span>截止日期</span
          ><strong :class="{ overdue: isOverdue(item) }"
            >{{ item.due_date || "未设置" }}{{ isOverdue(item) ? " · 已逾期" : "" }}</strong
          >
        </div>
        <div class="task-meta">
          <span>优先级</span
          ><ElTag :type="priorityType(item.priority)" size="small" effect="plain">{{
            priorities[item.priority ?? 1]
          }}</ElTag>
        </div>
        <div class="task-meta">
          <span>创建人</span><span>{{ item.created_by?.name || "—" }}</span>
        </div>
      </template>
      <template #footer="{ item }">
        <div class="task-actions">
          <ElButton size="small" @click="openDetail(item.id!)">详情</ElButton>
          <ElButton
            v-if="canEdit(item)"
            v-hasPerm="['module_system:ticket:update']"
            size="small"
            type="primary"
            plain
            @click="openEditor(item.id!)"
            >编辑</ElButton
          >
          <ElButton
            v-if="canEdit(item) && item.status === 0"
            v-hasPerm="['module_system:ticket:update']"
            size="small"
            type="primary"
            @click="changeStatus(item, 1)"
            >开始</ElButton
          >
          <ElButton
            v-if="canEdit(item) && item.status === 1"
            v-hasPerm="['module_system:ticket:update']"
            size="small"
            type="success"
            @click="changeStatus(item, 2)"
            >完成</ElButton
          >
        </div>
      </template>
    </ArgusCardGrid>

    <ElDialog
      v-model="editorVisible"
      :title="editingId ? '编辑任务' : '新建任务'"
      width="min(880px, 94vw)"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <ElFormItem label="任务标题" prop="title"
          ><ElInput
            v-model="form.title"
            maxlength="200"
            show-word-limit
            placeholder="例如：完成本周客户资料归档"
        /></ElFormItem>
        <div class="task-form-grid">
          <ElFormItem label="负责人"
            ><ElSelect
              v-model="form.assigned_id"
              filterable
              clearable
              placeholder="选择负责这项工作的同事"
              :disabled="!canAssign"
              class="w-full"
              ><ElOption
                v-for="user in assignees"
                :key="user.id"
                :value="user.id"
                :label="`${user.name || user.username} · ${user.username}`" /></ElSelect
          ></ElFormItem>
          <ElFormItem label="截止日期"
            ><ElDatePicker
              v-model="form.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择交付日期"
              class="w-full"
          /></ElFormItem>
          <ElFormItem label="优先级"
            ><ElSelect v-model="form.priority" class="w-full"
              ><ElOption
                v-for="(label, i) in priorities"
                :key="i"
                :label="label"
                :value="i" /></ElSelect
          ></ElFormItem>
          <ElFormItem label="任务类别"
            ><ElSelect v-model="form.ticket_type" class="w-full"
              ><ElOption
                v-for="option in categories"
                :key="option.value"
                :label="option.label"
                :value="option.value" /></ElSelect
          ></ElFormItem>
        </div>
        <ElFormItem label="任务描述"
          ><ArgusWangEditor
            v-model="form.ticket_content"
            height="240px"
            placeholder="描述工作目标、交付内容和验收要求，可插入图片。"
        /></ElFormItem>
        <ElFormItem label="任务附件"
          ><ArgusFileUpload v-model="attachment" tip="可上传一份参考文件，最大 20 MB。"
        /></ElFormItem>
      </ElForm>
      <template #footer
        ><ElButton @click="editorVisible = false">取消</ElButton
        ><ElButton type="primary" :loading="saving" @click="saveTask">保存任务</ElButton></template
      >
    </ElDialog>

    <ElDialog v-model="detailVisible" title="任务详情" width="min(880px, 94vw)" destroy-on-close>
      <template v-if="detail">
        <h3 class="mb-4 text-lg font-semibold">{{ detail.title }}</h3>
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="状态"
            ><ElTag :type="statusType(detail.status)">{{
              statuses[detail.status ?? 0]
            }}</ElTag></ElDescriptionsItem
          >
          <ElDescriptionsItem label="优先级">{{
            priorities[detail.priority ?? 1]
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="负责人">{{
            detail.assigned_by?.name || "待分配"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="截止日期"
            ><span :class="{ overdue: isOverdue(detail) }">{{
              detail.due_date || "未设置"
            }}</span></ElDescriptionsItem
          >
          <ElDescriptionsItem label="来源">{{
            detail.source_meeting_id ? "会议纪要" : "手动创建"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建人">{{
            detail.created_by?.name || "—"
          }}</ElDescriptionsItem>
          <ElDescriptionsItem label="类别">{{
            categories.find((c) => c.value === detail?.ticket_type)?.label || "其他"
          }}</ElDescriptionsItem>
        </ElDescriptions>
        <div
          class="task-content"
          v-html="DOMPurify.sanitize(detail.ticket_content || '<p>暂无详细描述</p>')"
        ></div>
        <ElLink
          v-if="detail.attachment_url"
          :href="detail.attachment_url"
          target="_blank"
          rel="noopener noreferrer"
          type="primary"
          >查看任务附件</ElLink
        >
        <ElDivider content-position="left">任务进展 · {{ commentsTotal }} 条评论</ElDivider>
        <div v-loading="commentsLoading">
          <div v-for="comment in comments" :key="comment.id" class="task-comment">
            <div>
              <strong>{{
                comment.created_by?.name || comment.created_by_name || "团队成员"
              }}</strong
              ><time>{{ comment.created_time }}</time>
            </div>
            <p class="whitespace-pre-wrap">{{ plainText(comment.content) }}</p>
          </div>
          <p v-if="!comments.length" class="task-muted">暂无评论，补充进展或需要协助的事项。</p>
          <ElButton
            v-if="comments.length < commentsTotal"
            text
            :loading="commentsLoading"
            @click="loadComments(true)"
            >加载更多评论</ElButton
          >
        </div>
        <ElInput
          v-model="commentText"
          type="textarea"
          :rows="3"
          maxlength="5000"
          show-word-limit
          placeholder="同步任务进展，或与同事讨论交付细节…"
          class="mt-4"
        />
        <div class="mt-3 flex justify-end">
          <ElButton
            type="primary"
            :loading="commentSaving"
            :disabled="!commentText.trim()"
            @click="sendComment"
            >发表评论</ElButton
          >
        </div>
      </template>
      <template #footer>
        <template v-if="detail && canEdit(detail)">
          <ElButton
            v-if="detail.status === 1"
            v-hasPerm="['module_system:ticket:update']"
            @click="changeStatus(detail, 0)"
            >移回待开始</ElButton
          >
          <ElButton
            v-if="detail.status === 2"
            v-hasPerm="['module_system:ticket:update']"
            @click="changeStatus(detail, 1)"
            >重新跟进</ElButton
          >
          <ElButton
            v-if="detail.status === 3 && canManage(detail)"
            v-hasPerm="['module_system:ticket:update']"
            @click="changeStatus(detail, 0)"
            >重新打开</ElButton
          >
          <ElButton
            v-if="detail.status !== 3 && canManage(detail)"
            v-hasPerm="['module_system:ticket:update']"
            type="warning"
            plain
            @click="changeStatus(detail, 3)"
            >取消任务</ElButton
          >
          <ElButton
            v-if="canManage(detail)"
            v-hasPerm="['module_system:ticket:delete']"
            type="danger"
            plain
            @click="removeTask(detail)"
            >删除任务</ElButton
          >
        </template>
        <ElButton @click="detailVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance } from "element-plus";
import DOMPurify from "dompurify";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@stores";
import TicketAPI, {
  getTicketComments,
  createTicketComment,
  type TicketTable,
  type TicketUpdateForm,
  type TicketCreateForm,
  type TicketCommentTable,
} from "@/api/module_system/ticket";
import ArgusCardGrid from "@/components/cards/argus-card-grid/index.vue";
import ArgusWangEditor from "@/components/forms/argus-wang-editor/index.vue";
import ArgusFileUpload from "@/components/forms/argus-file-upload/index.vue";

defineOptions({ name: "ModuleTicket" });
const userStore = useUserStore();
const statuses = ["待开始", "进行中", "已完成", "已取消"];
const priorities = ["低", "普通", "高", "紧急"];
const categories = [
  { label: "工作事项", value: "suggestion" },
  { label: "缺陷修复", value: "bug" },
  { label: "改进优化", value: "optimize" },
  { label: "其他", value: "other" },
];
const tasks = ref<TicketTable[]>([]);
const total = ref(0);
const pageNo = ref(1);
const pageSize = ref(12);
const loading = ref(false);
const view = ref<"all" | "assigned" | "created">("assigned");
const filters = reactive<{ title: string; status?: number | ""; priority?: number | "" }>({
  title: "",
});
let listRequest = 0;
function canManage(task: TicketTable) {
  return (
    !!userStore.info.is_superuser || (!!userStore.info.id && task.created_id === userStore.info.id)
  );
}
function canEdit(task: TicketTable) {
  return canManage(task) || (!!userStore.info.id && task.assigned_id === userStore.info.id);
}
function statusType(status?: number) {
  return (["info", "primary", "success", "warning"] as const)[status ?? 0];
}
function priorityType(priority?: number) {
  return (["info", "info", "warning", "danger"] as const)[priority ?? 1];
}
function plainText(html: string) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent?.trim() || "";
}
function isOverdue(task: TicketTable) {
  const today = new Date();
  const local = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return !!task.due_date && task.due_date < local && (task.status ?? 0) < 2;
}
async function fetchTasks() {
  const requestId = ++listRequest;
  loading.value = true;
  try {
    const res = await TicketAPI.listTicket({
      page_no: pageNo.value,
      page_size: pageSize.value,
      view: view.value,
      title: filters.title || undefined,
      status: filters.status === "" ? undefined : filters.status,
      priority: filters.priority === "" ? undefined : filters.priority,
    });
    if (requestId !== listRequest) return;
    tasks.value = res.data.data.items || [];
    total.value = res.data.data.total || 0;
  } finally {
    if (requestId === listRequest) loading.value = false;
  }
}
function resetPage() {
  pageNo.value = 1;
  void fetchTasks();
}
function changePage(page: number) {
  pageNo.value = page;
  void fetchTasks();
}
function changeSize(size: number) {
  pageSize.value = size;
  resetPage();
}
const assignees = ref<{ id: number; name: string; username: string }[]>([]);
const editorVisible = ref(false);
const editingId = ref<number>();
const editingTask = ref<TicketTable>();
const canAssign = computed(() => !editingTask.value || canManage(editingTask.value));
const saving = ref(false);
const formRef = ref<FormInstance>();
const emptyForm = () => ({
  title: "",
  ticket_content: "",
  ticket_type: "suggestion",
  priority: 1,
  due_date: null as string | null,
  assigned_id: null as number | null,
  attachment_url: null as string | null,
});
const form = reactive(emptyForm());
const attachment = computed({
  get: () => form.attachment_url || "",
  set: (url: string) => {
    form.attachment_url = url || null;
  },
});
const rules = {
  title: [{ required: true, whitespace: true, message: "请输入任务标题", trigger: "blur" }],
};
async function openEditor(id?: number) {
  editingId.value = id;
  editingTask.value = undefined;
  Object.assign(form, emptyForm());
  if (id) {
    const task = (await TicketAPI.detailTicket(id)).data.data;
    editingTask.value = task;
    Object.assign(form, {
      title: task.title,
      ticket_content: task.ticket_content || "",
      ticket_type: task.ticket_type,
      priority: task.priority ?? 1,
      due_date: task.due_date || null,
      assigned_id: task.assigned_id || null,
      attachment_url: task.attachment_url || null,
    });
  }
  assignees.value = (await TicketAPI.assignees()).data.data;
  editorVisible.value = true;
}
async function saveTask() {
  if (!(await formRef.value?.validate().catch(() => false))) return;
  saving.value = true;
  try {
    const payload = {
      ...form,
      assigned_id: form.assigned_id || null,
      due_date: form.due_date || null,
      summary: plainText(form.ticket_content).slice(0, 500),
    };
    if (editingId.value) {
      const update: TicketUpdateForm = { ...payload };
      if (!canAssign.value) delete update.assigned_id;
      await TicketAPI.updateTicket(editingId.value, update);
    } else {
      await TicketAPI.createTicket(payload as TicketCreateForm);
    }
    editorVisible.value = false;
    ElMessage.success("任务已保存");
    await fetchTasks();
  } finally {
    saving.value = false;
  }
}
const detailVisible = ref(false);
const detail = ref<TicketTable>();
const comments = ref<TicketCommentTable[]>([]);
const commentsTotal = ref(0);
const commentsLoading = ref(false);
const commentText = ref("");
const commentSaving = ref(false);
let commentPage = 1;
async function openDetail(id: number) {
  detail.value = (await TicketAPI.detailTicket(id)).data.data;
  comments.value = [];
  commentsTotal.value = 0;
  commentText.value = "";
  detailVisible.value = true;
  await loadComments();
}
async function loadComments(more = false) {
  const id = detail.value?.id;
  if (!id) return;
  const page = more ? commentPage + 1 : 1;
  commentsLoading.value = true;
  try {
    const result = (await getTicketComments(id, { page_no: page, page_size: 20 })).data.data;
    if (detail.value?.id !== id) return;
    comments.value = more ? [...comments.value, ...result.items] : result.items;
    commentsTotal.value = result.total;
    commentPage = page;
  } finally {
    commentsLoading.value = false;
  }
}
async function sendComment() {
  if (!detail.value?.id || !commentText.value.trim()) return;
  commentSaving.value = true;
  try {
    await createTicketComment(detail.value.id, { content: commentText.value.trim() });
    commentText.value = "";
    await loadComments();
  } finally {
    commentSaving.value = false;
  }
}
async function changeStatus(task: TicketTable, status: number) {
  if (status === 3) {
    try {
      await ElMessageBox.confirm(
        "取消后可由创建人或管理员重新打开，确认取消这项任务？",
        "取消任务",
        { type: "warning" }
      );
    } catch {
      return;
    }
  }
  await TicketAPI.updateTicket(task.id!, { status });
  ElMessage.success("任务状态已更新");
  if (detail.value?.id === task.id)
    detail.value = (await TicketAPI.detailTicket(task.id!)).data.data;
  await fetchTasks();
}
async function removeTask(task: TicketTable) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${task.title}」？`, "删除任务", { type: "warning" });
  } catch {
    return;
  }
  await TicketAPI.deleteTicket([task.id!]);
  detailVisible.value = false;
  ElMessage.success("任务已删除");
  await fetchTasks();
}
const route = useRoute();
const router = useRouter();
watch(
  () => [route.path, route.query.task_id] as const,
  ([path, id]) => {
    if (path === "/system/ticket" && typeof id === "string" && /^[1-9]\d*$/.test(id))
      void openDetail(Number(id));
  },
  { immediate: true }
);
watch(detailVisible, (visible) => {
  if (!visible && route.path === "/system/ticket" && route.query.task_id) {
    const query = { ...route.query };
    delete query.task_id;
    void router.replace({ path: route.path, query });
  }
});
watch(
  () => route.path,
  (path) => {
    if (path === "/system/ticket") void fetchTasks();
  },
  { immediate: true }
);
</script>

<style scoped>
.task-page {
  padding: 4px;
}
.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.task-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 650;
}
.task-header p,
.task-muted {
  color: var(--el-text-color-secondary);
}
.task-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.task-search {
  width: 220px;
}
.task-select {
  width: 140px;
}
.task-list-caption {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.task-list-caption span {
  color: var(--el-text-color-secondary);
}
.task-page :deep(.task-card-header) {
  display: flex;
  align-items: center;
  gap: 12px;
}
.task-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.task-summary {
  min-height: 42px;
  margin-bottom: 18px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
}
.task-meta > span:first-child {
  color: var(--el-text-color-secondary);
}
.task-meta strong {
  font-weight: 500;
}
.overdue {
  color: var(--el-color-danger);
}
.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.task-actions .el-button + .el-button {
  margin-left: 0;
}
.task-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}
.task-content {
  margin: 20px 0;
  overflow-wrap: anywhere;
}
.task-content :deep(img) {
  max-width: 100%;
}
.task-comment {
  margin: 12px 0;
  padding: 14px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
.task-comment > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}
.task-comment time {
  color: var(--el-text-color-secondary);
}
.task-comment p {
  margin-top: 8px;
  overflow-wrap: anywhere;
}
@media (width < 640px) {
  .task-header {
    align-items: flex-start;
  }
  .task-header p {
    font-size: 12px;
  }
  .task-form-grid {
    grid-template-columns: 1fr;
  }
  .task-search {
    width: 100%;
  }
  .task-list-caption span {
    display: none;
  }
}
</style>
