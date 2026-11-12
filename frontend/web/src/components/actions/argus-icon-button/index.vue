<!-- 按钮组件 -->
<template>
  <button
    type="button"
    class="argus-icon-button size-8.5 inline-flex items-center justify-center cursor-pointer border-0 bg-transparent p-0 text-g-600 dark:text-g-800 text-xl rounded-lg transition duration-300 hover:bg-hover-color"
    :class="{ 'rounded-full': circle }"
    :aria-label="ariaLabel || icon"
    :title="ariaLabel || icon"
  >
    <ArgusSvgIcon :icon="icon"></ArgusSvgIcon>
    <slot></slot>
  </button>
</template>

<script lang="ts" setup>
defineOptions({ name: "ArgusIconButton" });

interface Props {
  /** 图标名称 */
  icon: string;
  /** 圆角按钮 */
  circle?: boolean;
  /** 无障碍标签 / 悬停说明 */
  ariaLabel?: string;
}

withDefaults(defineProps<Props>(), {});
</script>

<style lang="scss" scoped>
.argus-icon-button {
  &:hover :deep(.argus-svg-icon) {
    color: var(--el-color-primary);
  }
}
</style>
