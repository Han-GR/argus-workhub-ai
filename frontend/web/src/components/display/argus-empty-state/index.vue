<!-- 空状态：图标 + 标题 + 说明 + 操作按钮（统一各页面空状态样式） -->
<template>
  <div class="argus-empty-state" :class="{ 'argus-empty-state--compact': compact }">
    <ArgusSvgIcon v-if="icon" class="argus-empty-state__icon" :icon="icon" />
    <div v-if="title" class="argus-empty-state__title">{{ title }}</div>
    <div v-if="description" class="argus-empty-state__desc">{{ description }}</div>
    <div v-if="$slots.default" class="argus-empty-state__actions">
      <slot />
    </div>
  </div>
</template>

<script lang="ts" setup>
defineOptions({
  name: "ArgusEmptyState",
  inheritAttrs: false,
});

withDefaults(
  defineProps<{
    /** 图标（ri: 图标名） */
    icon?: string;
    /** 主标题 */
    title?: string;
    /** 说明文字 */
    description?: string;
    /** 紧凑模式：用于侧栏、卡片内部 */
    compact?: boolean;
  }>(),
  {
    icon: "ri:inbox-line",
    title: "",
    description: "",
    compact: false,
  }
);
</script>
