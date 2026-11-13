<template>
  <div class="knowledge-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">TEAM KNOWLEDGE</span>
        <h1>知识库</h1>
        <p>沉淀公司制度与部门经验，从团队资料中找到答案。</p>
      </div>
      <div class="heading-actions">
        <ElButton v-if="catalog?.can_configure" @click="configVisible = true"
          >向量模型配置</ElButton
        >
        <ElButton v-if="catalog?.can_create" type="primary" @click="openCreate"
          >新建知识库</ElButton
        >
        <ElButton :loading="loading" @click="loadCatalog">刷新</ElButton>
      </div>
    </header>

    <div v-if="loadFailed" class="page-empty" role="alert">
      <p>知识库加载失败</p>
      <ElButton @click="loadCatalog">重试</ElButton>
    </div>
    <p v-else-if="loading" class="page-empty" role="status">正在加载知识库…</p>
    <div v-else class="knowledge-layout">
      <aside class="base-sidebar" aria-label="知识库列表">
        <h2>
          可访问的知识库 <span>{{ catalog?.bases.length || 0 }}</span>
        </h2>
        <p class="scope-hint">全公司及你所在部门的资料</p>
        <button
          v-for="base in catalog?.bases"
          :key="base.id"
          type="button"
          class="base-item"
          :class="{ selected: selectedId === base.id }"
          :aria-pressed="selectedId === base.id"
          @click="selectedId = base.id"
        >
          <strong>{{ base.name }}</strong>
          <span
            >{{ base.dept_id === null ? "全公司" : base.dept_name }} ·
            {{ base.can_manage ? "可维护" : "只读" }}</span
          >
        </button>
        <p v-if="!catalog?.bases.length" class="scope-hint">
          暂无可访问的知识库。请联系维护人创建。
        </p>
      </aside>

      <main v-if="selected" class="base-content">
        <div class="base-title">
          <div>
            <h2>{{ selected.name }}</h2>
            <ElTag :type="selected.dept_id === null ? 'primary' : 'info'">{{
              selected.dept_id === null ? "全公司可见" : `${selected.dept_name}可见`
            }}</ElTag>
          </div>
          <ElButton v-if="selected.can_manage" link type="danger" @click="deleteBase"
            >删除空知识库</ElButton
          >
        </div>
        <KnowledgeDocuments
          :key="`${selected.id}-${configVersion}`"
          :base-id="selected.id"
          :can-manage="selected.can_manage"
        />
      </main>
      <div v-else class="page-empty">
        <h2>团队的知识，从这里开始</h2>
        <p>选择一个知识库查看资料和提问。</p>
      </div>
    </div>

    <ElDialog
      v-model="createVisible"
      title="新建知识库"
      width="min(460px, 95vw)"
      append-to-body
      :close-on-click-modal="!creating"
      :close-on-press-escape="!creating"
      :show-close="!creating"
    >
      <ElForm label-position="top" @submit.prevent="createBase">
        <ElFormItem label="知识库名称"
          ><ElInput
            v-model="form.name"
            placeholder="请输入知识库名称"
            maxlength="100"
            :disabled="creating"
        /></ElFormItem>
        <ElFormItem label="可见范围">
          <ElSelect v-model="form.dept_id" aria-label="知识库可见范围" :disabled="creating">
            <ElOption v-if="catalog?.can_create_company" :value="0" label="全公司" />
            <ElOption
              v-for="dept in catalog?.departments"
              :key="dept.id"
              :value="dept.id"
              :label="dept.name"
            />
          </ElSelect>
        </ElFormItem>
        <p class="scope-hint">创建后可见范围固定。请按资料的共享范围选择知识库。</p>
      </ElForm>
      <template #footer
        ><ElButton :disabled="creating" @click="createVisible = false">取消</ElButton
        ><ElButton
          type="primary"
          :loading="creating"
          :disabled="!form.name.trim() || form.dept_id === null"
          @click="createBase"
          >创建</ElButton
        ></template
      >
    </ElDialog>
    <ArgusDrawer
      v-if="catalog?.can_configure"
      v-model="configVisible"
      title="企业向量模型配置"
      size="min(720px, 100vw)"
      @close="refreshIndexStatus"
    >
      <EmbeddingConfig v-if="configVisible" />
    </ArgusDrawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTag,
} from "element-plus";
import { KnowledgeAPI, type KnowledgeCatalog } from "@/api/module_ai/knowledge";
import KnowledgeDocuments from "./components/KnowledgeDocuments.vue";
import EmbeddingConfig from "./components/EmbeddingConfig.vue";

defineOptions({ name: "Knowledge" });
const catalog = ref<KnowledgeCatalog>();
const selectedId = ref("");
const selected = computed(() => catalog.value?.bases.find((base) => base.id === selectedId.value));
const loading = ref(false);
const loadFailed = ref(false);
const createVisible = ref(false);
const creating = ref(false);
const configVisible = ref(false);
const configVersion = ref(0);
const form = reactive<{ name: string; dept_id: number | null }>({ name: "", dept_id: null });

async function loadCatalog() {
  loading.value = true;
  loadFailed.value = true;
  try {
    const response = await KnowledgeAPI.catalog();
    if (response.data.code === 0) {
      catalog.value = response.data.data;
      if (!catalog.value.bases.some((base) => base.id === selectedId.value))
        selectedId.value = catalog.value.bases[0]?.id || "";
      loadFailed.value = false;
    }
  } catch {
    /* 请求层统一展示错误，页面提供重试。 */
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.name = "";
  form.dept_id = catalog.value?.can_create_company
    ? 0
    : (catalog.value?.departments[0]?.id ?? null);
  createVisible.value = true;
}

async function createBase() {
  if (creating.value || !form.name.trim() || form.dept_id === null || !catalog.value?.can_create)
    return;
  creating.value = true;
  try {
    const response = await KnowledgeAPI.createBase({
      name: form.name.trim(),
      dept_id: form.dept_id === 0 ? null : form.dept_id,
    });
    if (response.data.code === 0) {
      selectedId.value = response.data.data.id;
      createVisible.value = false;
      await loadCatalog();
    }
  } catch {
    /* 请求层统一展示错误。 */
  } finally {
    creating.value = false;
  }
}

async function deleteBase() {
  const base = selected.value;
  if (!base?.can_manage) return;
  try {
    await ElMessageBox.confirm(`删除「${base.name}」？仅空知识库可以删除。`, "删除知识库", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    const response = await KnowledgeAPI.deleteBase(base.id);
    if (response.data.code === 0) await loadCatalog();
  } catch {
    /* 请求层统一展示错误。 */
  }
}

function refreshIndexStatus() {
  configVersion.value += 1;
}
onMounted(loadCatalog);
</script>

<style scoped lang="scss">
.knowledge-page {
  padding: 24px;
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
  font-size: 11px;
  font-weight: 600;
  color: var(--el-color-primary);
  letter-spacing: 2px;
}
.page-heading h1 {
  margin: 8px 0;
  font-size: 28px;
}
.page-heading p,
.scope-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.8;
}
.heading-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.heading-actions :deep(.el-button) {
  margin: 0;
}
.knowledge-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: 560px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
}
.base-sidebar {
  padding: 24px 16px;
  border-right: 1px solid var(--el-border-color-lighter);
}
.base-sidebar h2 {
  margin: 0;
  font-size: 14px;
}
.base-sidebar h2 span {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
}
.base-item {
  display: block;
  width: 100%;
  padding: 14px;
  margin-top: 10px;
  text-align: left;
  cursor: pointer;
  color: var(--el-text-color-primary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  overflow-wrap: anywhere;
}
.base-item strong,
.base-item span {
  display: block;
}
.base-item span {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.base-item:hover {
  background: var(--el-fill-color-light);
}
.base-item.selected {
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
}
.base-item:focus-visible {
  outline: 2px solid var(--el-color-primary);
}
.base-content {
  min-width: 0;
  padding: 24px;
}
.base-title {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 24px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.base-title h2 {
  display: inline;
  margin-right: 12px;
  font-size: 18px;
  overflow-wrap: anywhere;
}
.page-empty {
  padding: 60px 24px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
@media (width <= 1000px) {
  .knowledge-layout {
    grid-template-columns: 1fr;
  }
  .base-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
}
@media (width <= 600px) {
  .knowledge-page {
    padding: 12px;
  }
  .base-content {
    padding: 16px;
  }
}
</style>
