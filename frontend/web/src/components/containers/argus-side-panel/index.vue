<!-- 侧边栏面板：标题 + 主操作 + 可选搜索 + 可滚动列表，供「左导航 + 右工作区」页面复用 -->
<template>
  <aside
    class="argus-side-panel flex min-h-0 shrink-0 flex-col"
    :class="variant === 'plain' ? 'argus-side-panel--plain' : 'argus-card'"
  >
    <div class="argus-side-panel__header">
      <span class="argus-panel-title">{{ title }}</span>
      <div v-if="$slots.actions" class="argus-side-panel__actions">
        <slot name="actions" />
      </div>
    </div>
    <div v-if="$slots.search" class="argus-side-panel__search">
      <slot name="search" />
    </div>
    <ElScrollbar class="min-h-0 flex-1">
      <slot />
    </ElScrollbar>
    <div v-if="$slots.footer" class="argus-side-panel__footer">
      <slot name="footer" />
    </div>
  </aside>
</template>

<script setup lang="ts">
defineOptions({ name: "ArgusSidePanel" });

withDefaults(
  defineProps<{
    /** 面板标题 */
    title: string;
    /** card：独立卡片；plain：作为工作区左栏，仅保留右侧分割线 */
    variant?: "card" | "plain";
  }>(),
  { variant: "card" }
);
</script>

<style lang="scss" scoped>
.argus-side-panel {
  width: var(--argus-side-panel-width, 216px);
  padding: 10px 8px;
}

/* 工作区左栏：无卡片外观，只有右侧分割线 */
.argus-side-panel--plain {
  height: 100%;
  background: transparent;
  border: 0;
  border-right: 1px solid var(--argus-border, #e6e8ec);
  border-radius: 0;
  box-shadow: none;
}

@media (width <= 1280px) {
  .argus-side-panel--plain {
    border-right: 0;
    border-bottom: 1px solid var(--argus-border, #e6e8ec);
  }
}

.argus-side-panel__header {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 8px;
}

.argus-side-panel__actions {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.argus-side-panel__search {
  padding: 0 2px 8px;
}

.argus-side-panel__footer {
  padding-top: 8px;
  border-top: 1px solid var(--argus-border-subtle, #eef0f3);
}
</style>
