<template>
  <main class="argus-workspace">
    <header class="workspace-heading">
      <div>
        <p class="workspace-eyebrow">ARGUS / WORKSPACE</p>
        <h1>{{ displayName }}，欢迎回来</h1>
        <p class="workspace-intro">集中管理工作文件，跟进协作事项，让 AI 帮你整理信息。</p>
      </div>
      <span class="workspace-date">{{ today }}</span>
    </header>

    <section aria-labelledby="workspace-tools-title">
      <div class="workspace-section-heading">
        <h2 id="workspace-tools-title">开始工作</h2>
        <span>文件 · 协作 · 智能助手</span>
      </div>
      <div v-if="availableTools.length" class="workspace-tools">
        <button
          v-for="tool in availableTools"
          :key="tool.route"
          type="button"
          class="workspace-tool"
          @click="router.push({ name: tool.route })"
        >
          <ArgusSvgIcon :icon="tool.icon" class="workspace-tool-icon" />
          <span class="workspace-tool-title">{{ tool.title }}</span>
          <span class="workspace-tool-description">{{ tool.description }}</span>
          <span class="workspace-tool-action"
            >进入{{ tool.title }} <span aria-hidden="true">↗</span></span
          >
        </button>
      </div>
      <ElEmpty v-else description="当前账号暂无业务访问权限，请联系管理员分配角色。" />
    </section>

    <section class="workspace-guide" aria-labelledby="workspace-guide-title">
      <div>
        <p class="workspace-eyebrow">WORKFLOW</p>
        <h2 id="workspace-guide-title">从一份文件，到一次协作</h2>
        <p>把资料和讨论留在工作空间中，方便团队查找与跟进。</p>
      </div>
      <ol>
        <li><strong>01 / 归集资料</strong><span>在文件管理中上传、浏览和下载工作文件。</span></li>
        <li>
          <strong>02 / 跟进事项</strong><span>明确负责人和交付时间，通过状态与评论跟进任务。</span>
        </li>
        <li>
          <strong>03 / 整理信息</strong><span>在智能对话中提问、整理文本，并查看历史会话。</span>
        </li>
      </ol>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@stores";
import { useAuth } from "@/hooks/core/useAuth";

defineOptions({ name: "Home", inheritAttrs: false });
const router = useRouter();
const userStore = useUserStore();
const { hasAuth } = useAuth();
const displayName = computed(() => userStore.info?.name || userStore.info?.username || "你好");
const today = new Intl.DateTimeFormat("zh-CN", {
  month: "long",
  day: "numeric",
  weekday: "long",
}).format(new Date());
const tools = [
  {
    title: "档案文件",
    description: "集中归集工作资料，浏览文件、管理目录并共享下载。",
    icon: "ri:folder-open-line",
    route: "WorkflowBrowse",
    permission: "module_task:storage:browse:query",
  },
  {
    title: "任务协同",
    description: "分配团队任务，设置优先级与截止日期，同步工作进展。",
    icon: "ri:task-line",
    route: "ModuleTicket",
    permission: "module_system:ticket:query",
  },
  {
    title: "AI 助手",
    description: "通过智能对话整理文本、解答问题，保留连续的会话记录。",
    icon: "ri:chat-ai-line",
    route: "Chat",
    permission: "module_ai:chat:query",
  },
];
const availableTools = computed(() =>
  tools.filter((tool) => router.hasRoute(tool.route) && hasAuth(tool.permission))
);
</script>

<style scoped>
.argus-workspace {
  max-width: 1280px;
  padding: 24px 12px 48px;
  margin: 0 auto;
  color: var(--el-text-color-primary);
}

.workspace-heading {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 36px;
}

.workspace-eyebrow {
  margin: 0 0 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.16em;
}

h1 {
  margin: 0 0 14px;
  font-size: clamp(24px, 3vw, 34px);
  font-weight: 600;
  letter-spacing: -0.03em;
}

.workspace-intro,
.workspace-guide p {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
}

.workspace-date {
  flex-shrink: 0;
  padding-top: 28px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.workspace-section-heading {
  display: flex;
  gap: 16px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
}

h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.workspace-section-heading > span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.workspace-tools {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.workspace-tool {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 28px;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  transition:
    border-color 160ms,
    background 160ms;
}

.workspace-tool:hover {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
}

.workspace-tool:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 4px;
}

.workspace-tool-icon {
  margin-bottom: 24px;
  font-size: 28px;
  color: var(--el-color-primary);
}

.workspace-tool-title {
  margin-bottom: 12px;
  font-size: 20px;
  font-weight: 600;
}

.workspace-tool-description {
  flex: 1;
  font-size: 13px;
  line-height: 1.9;
  color: var(--el-text-color-secondary);
}

.workspace-tool-action {
  display: flex;
  align-self: stretch;
  justify-content: space-between;
  padding-top: 18px;
  margin-top: 28px;
  font-size: 13px;
  color: var(--el-color-primary);
  border-top: 1px solid var(--el-border-color-lighter);
}

.workspace-guide {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 40px;
  padding: 32px;
  margin-top: 36px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
}

.workspace-guide ol {
  display: grid;
  gap: 24px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.workspace-guide li {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.workspace-guide li span {
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
@media (width <= 800px) {
  .workspace-tools,
  .workspace-guide {
    grid-template-columns: 1fr;
  }

  .workspace-heading {
    flex-direction: column;
    gap: 4px;
  }

  .workspace-date {
    padding-top: 0;
  }

  .workspace-section-heading > span {
    display: none;
  }

  .workspace-guide {
    padding: 24px;
  }
}
</style>
