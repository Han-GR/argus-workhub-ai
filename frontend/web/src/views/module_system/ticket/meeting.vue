<template>
  <div class="meeting-page">
    <header class="meeting-header">
      <h1>会议纪要</h1>
      <p>从会议记录中整理待办，核对负责人和截止时间后，一键创建任务。</p>
    </header>
    <section class="meeting-panel" :aria-busy="busy">
      <ElAlert
        v-if="!canExtract"
        title="提取会议任务需要 AI 助手访问权限，请联系管理员开通。"
        type="warning"
        :closable="false"
        class="mb-6"
      />
      <ElSteps :active="step - 1" finish-status="success" align-center class="mb-6">
        <ElStep title="粘贴纪要" /><ElStep title="核对任务" /><ElStep title="创建完成" />
      </ElSteps>
      <template v-if="step === 1">
        <ElForm label-position="top">
          <ElFormItem label="会议日期"
            ><ElDatePicker
              v-model="referenceDate"
              value-format="YYYY-MM-DD"
              :clearable="false"
              :disabled="busy"
            /><span class="meeting-hint ml-3">“明天、下周五”等日期以此为准。</span></ElFormItem
          >
          <ElFormItem label="会议记录"
            ><ElInput
              v-model="source"
              type="textarea"
              :rows="12"
              maxlength="20000"
              show-word-limit
              :disabled="busy"
              placeholder="粘贴会议记录，例如：小王负责整理客户资料，下周五前完成；小李跟进合同审批，截止日期待确认。"
          /></ElFormItem>
        </ElForm>
        <p class="meeting-hint">
          AI 仅生成草稿。负责人、截止日期和任务内容均可修改，人工确认后才会创建任务。
        </p>
        <p v-if="extracting" class="meeting-hint">正在提取并校验任务，最多等待约两分钟…</p>
      </template>
      <template v-else-if="step === 2">
        <ElAlert
          v-for="warning in warnings"
          :key="warning"
          :title="warning"
          type="warning"
          show-icon
          :closable="false"
          class="mb-3"
        />
        <details class="meeting-source">
          <summary>查看会议原文 · {{ referenceDate }}</summary>
          <p>{{ source }}</p>
        </details>
        <div class="meeting-review-heading">
          <strong>任务草稿 · 已选 {{ selected.length }} / {{ rows.length }}</strong
          ><ElButton :disabled="busy || rows.length >= 20" @click="addRow">手动添加任务</ElButton>
        </div>
        <ElEmpty
          v-if="!rows.length"
          description="暂未生成任务，可手动添加后确认创建。"
          :image-size="64"
        />
        <ElForm label-position="top" :disabled="saving">
          <section v-for="(row, index) in rows" :key="row.key" class="meeting-task-row">
            <div class="meeting-row-heading">
              <ElCheckbox v-model="row.selected">任务 {{ index + 1 }}</ElCheckbox
              ><ElButton text type="danger" :disabled="busy" @click="removeRow(row.key)"
                >移除</ElButton
              >
            </div>
            <ElInput
              v-model="row.title"
              maxlength="200"
              show-word-limit
              placeholder="任务标题"
              class="mb-3"
            />
            <ElInput
              v-model="row.description"
              type="textarea"
              :rows="2"
              maxlength="4000"
              placeholder="工作目标、交付内容和验收要求"
              class="mb-3"
            />
            <div class="meeting-fields">
              <ElFormItem label="负责人"
                ><ElSelect
                  v-model="row.assigned_id"
                  filterable
                  clearable
                  placeholder="待确认，请选择同事"
                  class="w-full"
                  ><ElOption
                    v-for="user in assignees"
                    :key="user.id"
                    :label="`${user.name || user.username} · ${user.username}`"
                    :value="user.id" /></ElSelect
                ><small v-if="row.owner_name">原文：{{ row.owner_name }}</small></ElFormItem
              >
              <ElFormItem label="截止日期"
                ><ElDatePicker
                  v-model="row.due_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="待确认，请选择日期"
                  class="w-full"
                /><small v-if="row.due_text">原文：{{ row.due_text }}</small></ElFormItem
              >
              <ElFormItem label="优先级"
                ><ElSelect v-model="row.priority" class="w-full"
                  ><ElOption
                    v-for="(label, i) in priorities"
                    :key="i"
                    :label="label"
                    :value="i" /></ElSelect
              ></ElFormItem>
            </div>
            <div class="flex flex-wrap gap-2 mb-2">
              <ElTag v-if="!row.assigned_id" type="warning" size="small">负责人待确认</ElTag
              ><ElTag v-if="!row.due_date" type="warning" size="small">截止时间待确认</ElTag
              ><ElTag
                v-if="row.due_date && row.due_date < referenceDate"
                type="warning"
                size="small"
                >截止日期早于会议日期</ElTag
              >
            </div>
            <blockquote v-if="row.evidence">原文依据：{{ row.evidence }}</blockquote>
            <p v-else class="meeting-hint">
              {{ row.manual ? "手动补充的任务" : "未找到可核验的原文依据，请核对任务内容。" }}
            </p>
          </section>
        </ElForm>
        <div class="meeting-confirmation">
          <ElCheckbox v-model="reviewed" :disabled="busy"
            >我已核对所选任务的内容、负责人和日期</ElCheckbox
          >
          <p>未选择负责人或日期的任务将保留为“待分配”或“未设置截止日期”。</p>
        </div>
        <ElAlert
          v-if="submitUncertain"
          title="尚未确认本次提交结果。可再次确认，系统会返回同一批次的创建结果，不会重复建任务。"
          type="warning"
          :closable="false"
          class="mt-3"
        />
      </template>
      <template v-else>
        <ElResult
          icon="success"
          :title="`已创建 ${createdIds.length} 项任务`"
          sub-title="任务已进入协同列表；分配给其他同事的任务会产生站内提醒。"
        >
          <template #extra
            ><div class="flex flex-wrap justify-center gap-2">
              <ElButton v-for="id in createdIds" :key="id" @click="viewTask(id)"
                >查看任务 #{{ id }}</ElButton
              >
            </div></template
          >
        </ElResult>
      </template>
      <footer class="meeting-footer">
        <template v-if="step === 1"
          ><ElButton
            type="primary"
            :loading="extracting"
            :disabled="!canExtract || !source.trim() || !referenceDate"
            @click="extract"
            >提取任务草稿</ElButton
          ></template
        >
        <template v-else-if="step === 2"
          ><ElButton :disabled="busy" @click="step = 1">返回修改纪要</ElButton
          ><ElButton
            type="primary"
            :loading="saving"
            :disabled="!reviewed || !selected.length"
            @click="confirm"
            >确认创建 {{ selected.length }} 项任务</ElButton
          ></template
        >
        <template v-else
          ><ElButton @click="startNew">新会议</ElButton
          ><ElButton type="primary" @click="router.push({ name: 'ModuleTicket' })"
            >返回我的任务</ElButton
          ></template
        >
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@stores";
import { ElMessage, ElMessageBox } from "element-plus";
import MeetingAPI, {
  type MeetingDraft,
  type MeetingDraftItem,
  type MeetingTaskItem,
} from "@/api/module_system/meeting-tasks";
import TicketAPI from "@/api/module_system/ticket";

defineOptions({ name: "MeetingMinutes" });
const userStore = useUserStore();
const canExtract = computed(
  () => !!userStore.info.is_superuser || userStore.prems.includes("module_ai:chat:query")
);
const router = useRouter();
const step = ref(1);
const source = ref("");
function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
const referenceDate = ref(localDate());
const draftId = ref<string>();
const warnings = ref<string[]>([]);
const priorities = ["低", "普通", "高", "紧急"];
const extracting = ref(false);
const saving = ref(false);
const busy = computed(() => extracting.value || saving.value);
const reviewed = ref(false);
const submitUncertain = ref(false);
const createdIds = ref<number[]>([]);
let rowKey = 0;
type ReviewRow = MeetingDraftItem & { key: number; selected: boolean; manual?: boolean };
const rows = ref<ReviewRow[]>([]);
const selected = computed(() => rows.value.filter((row) => row.selected));
const assignees = ref<{ id: number; name: string; username: string }[]>([]);
watch(
  rows,
  () => {
    reviewed.value = false;
  },
  { deep: true }
);
async function loadAssignees() {
  try {
    assignees.value = (await TicketAPI.assignees()).data.data;
  } catch {
    /* 允许保留未分配的任务，HTTP层会提示目录加载失败。 */
  }
}
function startNew() {
  step.value = 1;
  source.value = "";
  draftId.value = undefined;
  rows.value = [];
  warnings.value = [];
  createdIds.value = [];
  reviewed.value = false;
  submitUncertain.value = false;
  referenceDate.value = localDate();
}
function addRow() {
  if (rows.value.length >= 20) return;
  rows.value.push({
    key: ++rowKey,
    selected: true,
    manual: true,
    title: "",
    description: "",
    assigned_id: null,
    due_date: null,
    priority: 1,
    evidence: "",
    warnings: [],
  });
}
function removeRow(key: number) {
  rows.value = rows.value.filter((row) => row.key !== key);
}
function acceptResult(ids: number[]) {
  createdIds.value = ids;
  submitUncertain.value = false;
  step.value = 3;
}
function applyDraft(result: MeetingDraft) {
  draftId.value = result.id;
  if (result.confirmed) {
    acceptResult(result.created_task_ids || []);
    return;
  }
  rows.value = result.tasks.map((row) => ({ ...row, key: ++rowKey, selected: true }));
  warnings.value = result.warnings;
  step.value = 2;
  submitUncertain.value = false;
}
async function extract() {
  if (!canExtract.value || busy.value) return;
  if (source.value.trim().length < 10) {
    ElMessage.warning("请提供至少10个字的会议记录");
    return;
  }
  if (rows.value.length) {
    try {
      await ElMessageBox.confirm("重新提取会替换当前未创建的草稿，是否继续？", "重新提取", {
        type: "warning",
      });
    } catch {
      return;
    }
  }
  extracting.value = true;
  try {
    applyDraft(
      (
        await MeetingAPI.extract({
          source_text: source.value.trim(),
          reference_date: referenceDate.value,
          draft_id: draftId.value,
        })
      ).data.data
    );
  } finally {
    extracting.value = false;
  }
}
async function confirm() {
  if (!reviewed.value || !draftId.value || !selected.value.length) return;
  if (selected.value.some((row) => !row.title.trim())) {
    ElMessage.warning("请填写所选任务的标题");
    return;
  }
  const tasks: MeetingTaskItem[] = selected.value.map((row) => ({
    title: row.title.trim(),
    description: row.description || "",
    assigned_id: row.assigned_id || null,
    due_date: row.due_date || null,
    priority: row.priority,
  }));
  saving.value = true;
  try {
    acceptResult((await MeetingAPI.confirm(draftId.value, tasks)).data.data.task_ids);
  } catch {
    submitUncertain.value = true;
    try {
      const stored = (await MeetingAPI.get(draftId.value)).data.data;
      if (stored.confirmed) acceptResult(stored.created_task_ids || []);
    } catch {
      /* 保留草稿与批次ID，允许按原批次重试。 */
    }
  } finally {
    saving.value = false;
  }
}
async function viewTask(id: number) {
  await router.push({ path: "/system/ticket", query: { task_id: id } });
}
onMounted(loadAssignees);
</script>

<style scoped>
.meeting-page {
  max-width: 1100px;
  padding: 28px;
  margin: 0 auto;
  color: var(--el-text-color-primary);
}
.meeting-header {
  margin-bottom: 28px;
}
.meeting-header h1 {
  margin: 0 0 10px;
  font-size: 26px;
}
.meeting-header p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.meeting-panel {
  padding: 28px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
}
.meeting-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: flex-end;
  padding-top: 24px;
  margin-top: 20px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.meeting-footer :deep(.el-button + .el-button) {
  margin-left: 0;
}
@media (width <= 600px) {
  .meeting-page {
    padding: 12px;
  }
  .meeting-panel {
    padding: 20px 16px;
  }
}

.meeting-hint,
.meeting-fields small {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.meeting-source {
  padding: 12px 16px;
  margin-bottom: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.meeting-source summary {
  cursor: pointer;
  color: var(--el-text-color-regular);
}
.meeting-source p {
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
  font-size: 13px;
  line-height: 1.8;
  margin-top: 12px;
}
.meeting-review-heading,
.meeting-row-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.meeting-task-row {
  padding: 18px;
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
}
.meeting-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.meeting-fields :deep(.el-form-item__content) {
  display: block;
}
.meeting-fields :deep(.el-date-editor) {
  width: 100%;
}
.meeting-fields small {
  display: block;
  margin-top: 4px;
}
.meeting-task-row blockquote {
  margin: 10px 0 0;
  padding: 8px 12px;
  border-left: 3px solid var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.meeting-confirmation {
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.meeting-confirmation p {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
@media (width < 640px) {
  .meeting-fields {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .meeting-task-row {
    padding: 12px;
  }
  .meeting-confirmation :deep(.el-checkbox__label) {
    white-space: normal;
  }
}
</style>
