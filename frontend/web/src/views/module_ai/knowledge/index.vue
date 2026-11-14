<template>
  <div class="knowledge-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">团队知识库 / 资料</span>
        <h1>文档管理</h1>
        <p>上传团队资料，选择共享范围，并管理自己上传的文件。</p>
      </div>
      <ElButton v-if="workspace?.can_configure" @click="configVisible = true"
        >向量模型配置</ElButton
      >
    </header>
    <div v-if="loadFailed" class="page-empty" role="alert">
      <p>知识库加载失败</p>
      <ElButton @click="loadWorkspace">重试</ElButton>
    </div>
    <p v-else-if="loading" class="page-empty" role="status">正在加载知识库…</p>
    <KnowledgeDocuments
      v-else-if="workspace"
      :key="configVersion"
      :department-name="workspace.department?.name || null"
    />
    <ArgusDrawer
      v-if="workspace?.can_configure"
      v-model="configVisible"
      title="企业向量模型配置"
      size="min(720px, 100vw)"
      @close="configVersion += 1"
    >
      <EmbeddingConfig v-if="configVisible" />
    </ArgusDrawer>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElButton } from "element-plus";
import { KnowledgeAPI, type KnowledgeWorkspace } from "@/api/module_ai/knowledge";
import KnowledgeDocuments from "./components/KnowledgeDocuments.vue";
import EmbeddingConfig from "./components/EmbeddingConfig.vue";
defineOptions({ name: "KnowledgeDocuments" });
const workspace = ref<KnowledgeWorkspace>();
const loading = ref(false);
const loadFailed = ref(false);
const configVisible = ref(false);
const configVersion = ref(0);
async function loadWorkspace() {
  loading.value = true;
  loadFailed.value = true;
  try {
    const response = await KnowledgeAPI.workspace();
    if (response.data.code === 0) {
      workspace.value = response.data.data;
      loadFailed.value = false;
    }
  } catch {
    /* 请求层统一提示，保留重试入口。 */
  } finally {
    loading.value = false;
  }
}
onMounted(loadWorkspace);
</script>
<style scoped lang="scss">
.knowledge-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 28px;
  color: var(--el-text-color-primary);
}
.page-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}
.eyebrow {
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
}
.page-heading h1 {
  margin: 8px 0;
  font-size: 26px;
}
.page-heading p {
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
}
.page-empty {
  padding: 60px 24px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
@media (width <= 600px) {
  .knowledge-page {
    padding: 12px;
  }
}
</style>
