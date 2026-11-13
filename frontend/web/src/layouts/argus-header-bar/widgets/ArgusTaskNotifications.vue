<template>
  <ElPopover
    v-if="canRead"
    v-model:visible="popoverVisible"
    placement="bottom-end"
    trigger="click"
    :width="380"
    popper-class="task-notification-popover"
    @show="loadInbox()"
  >
    <template #reference>
      <ElBadge :value="unread" :hidden="!unread" :max="99" class="task-message-badge">
        <ArgusIconButton icon="ri:notification-3-line" :aria-label="`任务消息，${unread}条未读`" />
      </ElBadge>
    </template>
    <div class="task-message-heading">
      <strong>任务消息</strong
      ><ElButton text size="small" :disabled="!unread || marking" @click="markAll"
        >全部已读</ElButton
      >
    </div>
    <ElScrollbar max-height="440px" v-loading="loading">
      <p v-if="!items.length && !loading" class="task-message-empty">暂无任务消息</p>
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="task-message-item"
        :class="{ unread: !item.is_read }"
        @click="openTask(item)"
      >
        <div class="task-message-title">
          <span>{{ item.title }}</span
          ><i v-if="!item.is_read" aria-label="未读"></i>
        </div>
        <p>{{ item.message }}</p>
        <time>{{ item.created_time }}</time>
      </button>
      <ElButton
        v-if="items.length < total"
        text
        class="w-full"
        :loading="loading"
        @click="loadInbox(false)"
        >加载更多</ElButton
      >
    </ElScrollbar>
    <div class="task-message-hint">分配、评论及进展提醒 · 截止提醒每分钟检查</div>
  </ElPopover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@stores";
import TaskMessages, { type TaskNotification } from "@/api/module_system/task-notification";

const router = useRouter();
const user = useUserStore();
const canRead = computed(
  () =>
    user.isLogin &&
    !!user.info.id &&
    (user.info.is_superuser || user.prems.includes("module_system:ticket:query"))
);
const popoverVisible = ref(false);
const unread = ref(0);
const items = ref<TaskNotification[]>([]);
const total = ref(0);
const loading = ref(false);
const marking = ref(false);
let page = 1;
let timer: ReturnType<typeof setInterval> | undefined;
let countVersion = 0;
async function refreshCount() {
  if (!canRead.value) return;
  const uid = user.info.id,
    version = ++countVersion;
  try {
    const result = await TaskMessages.count();
    if (canRead.value && uid === user.info.id && version === countVersion)
      unread.value = result.data.data;
  } catch {
    /* HTTP 层统一处理认证与网络错误。 */
  }
}
async function loadInbox(reset = true) {
  if (!canRead.value || loading.value) return;
  const uid = user.info.id,
    nextPage = reset ? 1 : page + 1;
  loading.value = true;
  try {
    const result = (await TaskMessages.list(nextPage)).data.data;
    if (!canRead.value || user.info.id !== uid) return;
    page = nextPage;
    items.value = reset ? result.items : [...items.value, ...result.items];
    total.value = result.total;
    ++countVersion;
    unread.value = result.unread;
  } finally {
    loading.value = false;
  }
}
async function markAll() {
  marking.value = true;
  try {
    await TaskMessages.readAll();
    ++countVersion;
    unread.value = 0;
    items.value.forEach((item) => {
      item.is_read = true;
    });
  } finally {
    marking.value = false;
  }
}
async function openTask(item: TaskNotification) {
  if (!item.is_read) {
    await TaskMessages.read(item.id);
    item.is_read = true;
    ++countVersion;
    unread.value = Math.max(0, unread.value - 1);
  }
  popoverVisible.value = false;
  await router.push({ path: "/system/ticket", query: { task_id: item.ticket_id } });
}
watch(
  () => `${canRead.value}:${user.info.id}`,
  () => {
    if (timer) clearInterval(timer);
    ++countVersion;
    unread.value = 0;
    items.value = [];
    total.value = 0;
    if (canRead.value) {
      void refreshCount();
      timer = setInterval(() => {
        void refreshCount();
      }, 60_000);
    }
  },
  { immediate: true }
);
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
  ++countVersion;
});
</script>

<style scoped>
.task-message-badge {
  display: inline-flex;
  align-items: center;
}
.task-message-badge :deep(.el-badge__content) {
  top: 8px;
  right: 8px;
}
.task-message-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.task-message-item {
  display: block;
  width: 100%;
  padding: 14px 8px;
  text-align: left;
  color: var(--el-text-color-regular);
  border: 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: transparent;
  cursor: pointer;
}
.task-message-item:hover {
  background: var(--el-fill-color-light);
}
.task-message-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-message-title span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-message-title i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
}
.task-message-item.unread .task-message-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.task-message-item p {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.5;
}
.task-message-item time,
.task-message-hint,
.task-message-empty {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.task-message-hint {
  padding-top: 12px;
}
.task-message-empty {
  padding: 28px 8px;
  text-align: center;
}
</style>
<style>
.task-notification-popover {
  max-width: calc(100vw - 24px);
}
</style>
