<!-- 工作区：FastHub 式「左卡片 + 间距 + 右卡片」，固定宽度、不提供拖拽与分割线 -->
<template>
  <div
    class="argus-workbench"
    :style="{
      '--argus-workbench-side-w': `${sideWidth}px`,
      '--argus-workbench-side-h': `${sideHeight}px`,
    }"
  >
    <div class="argus-workbench__side">
      <slot name="side" />
    </div>
    <div class="argus-workbench__main">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "ArgusWorkbench" });

withDefaults(
  defineProps<{
    /** 左栏宽度（水平布局） */
    sideWidth?: number;
    /** 窄屏上下布局时上栏高度 */
    sideHeight?: number;
  }>(),
  {
    sideWidth: 380,
    sideHeight: 320,
  }
);
</script>

<style lang="scss" scoped>
.argus-workbench {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0;
}

.argus-workbench__side {
  display: flex;
  flex: 0 0 auto;
  width: var(--argus-workbench-side-w);
  min-width: 0;
  min-height: 0;
}

.argus-workbench__side > * {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
}

.argus-workbench__main {
  box-sizing: border-box;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.argus-workbench__main > * {
  flex: 1 1 auto;
  min-height: 0;
}

@media (width <= 1280px) {
  .argus-workbench {
    flex-direction: column;
  }

  .argus-workbench__side {
    width: 100%;
    height: var(--argus-workbench-side-h);
  }
}
</style>
