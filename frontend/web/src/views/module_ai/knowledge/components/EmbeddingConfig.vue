<template>
  <section v-loading="loading" class="embedding-config">
    <div class="embedding-heading">
      <div>
        <h3>向量模型配置</h3>
        <p>将文本转换为向量，用于知识库的语义检索。</p>
      </div>
      <ElTag :type="availableSavedKey ? 'success' : 'info'">{{
        availableSavedKey ? "已配置" : "未配置"
      }}</ElTag>
    </div>

    <ElAlert
      title="全公司共用此向量模型，由超级管理员统一维护。"
      description="测试会向所选服务商发送一段固定短文本，按该服务商的额度和计费规则执行。"
      type="info"
      :closable="false"
      show-icon
    />

    <ElForm ref="formRef" :model="form" :rules="rules" label-position="top" class="embedding-form">
      <ElFormItem label="服务商">
        <ElSelect
          :model-value="form.base_url"
          :disabled="busy || loading"
          aria-label="服务商"
          @change="changeProvider"
        >
          <ElOption label="硅基流动 · BGE-M3" :value="SILICONFLOW_BASE_URL" />
          <ElOption label="智谱 AI · Embedding-3" :value="ZHIPU_BASE_URL" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="Base URL">
        <ElInput :model-value="form.base_url" readonly />
      </ElFormItem>
      <ElFormItem label="API Key" prop="api_key">
        <ElInput
          v-model="form.api_key"
          type="password"
          show-password
          autocomplete="new-password"
          :placeholder="
            availableSavedKey ? '已保存密钥，留空保持不变' : '请输入当前服务商的 API Key'
          "
          :disabled="busy"
        />
      </ElFormItem>
      <div class="embedding-options">
        <ElFormItem label="模型">
          <ElInput :model-value="form.model_id" readonly />
        </ElFormItem>
        <ElFormItem label="向量维度">
          <ElSelect
            v-model="form.dimensions"
            :disabled="busy || isSiliconflow"
            aria-label="向量维度"
          >
            <ElOption
              v-for="dimension in [256, 512, 1024, 2048]"
              :key="dimension"
              :label="`${dimension} 维`"
              :value="dimension"
            />
          </ElSelect>
        </ElFormItem>
      </div>
      <p class="embedding-hint">
        {{
          isSiliconflow ? "BGE-M3 固定使用 1024 维。" : "默认使用 1024 维。"
        }}更换模型或向量维度后，所有已有文档需要重新建立索引。
      </p>
      <ElAlert
        v-if="testResult"
        :title="`向量测试通过 · ${testResult.dimensions} 维 · ${testResult.latency_ms} ms`"
        type="success"
        :closable="false"
        show-icon
      />
      <div class="embedding-actions">
        <ElButton
          :loading="testing"
          :disabled="busy || loading || loadFailed"
          @click="testConnection"
          >测试连接</ElButton
        >
        <ElButton
          type="primary"
          :loading="saving"
          :disabled="busy || loading || loadFailed"
          @click="save"
          >保存配置</ElButton
        >
      </div>
      <ElButton v-if="loadFailed" link type="primary" @click="loadConfig"
        >加载失败，点击重试</ElButton
      >
    </ElForm>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import {
  EmbeddingAPI,
  type EmbeddingConfigInput,
  type EmbeddingTestResult,
} from "@/api/module_ai/embedding";

const SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1";
const ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4";
const form = reactive<EmbeddingConfigInput>({
  base_url: SILICONFLOW_BASE_URL,
  model_id: "BAAI/bge-m3",
  dimensions: 1024,
  api_key: "",
});
const formRef = ref<FormInstance>();
const loading = ref(true);
const loadFailed = ref(false);
const hasApiKey = ref(false);
const savedBaseUrl = ref("");
const isSiliconflow = computed(() => form.base_url === SILICONFLOW_BASE_URL);
const availableSavedKey = computed(() => hasApiKey.value && savedBaseUrl.value === form.base_url);
const saving = ref(false);
const testing = ref(false);
const busy = computed(() => saving.value || testing.value);
const testResult = ref<EmbeddingTestResult | null>(null);
const rules: FormRules = {
  api_key: [
    {
      validator: (_rule, value: string, callback) => {
        if (!value && !availableSavedKey.value) callback(new Error("请输入当前服务商的 API Key"));
        else if (value && /\s/.test(value)) callback(new Error("API Key 不能包含空白字符"));
        else callback();
      },
      trigger: "blur",
    },
  ],
};

watch(form, () => {
  testResult.value = null;
});

function changeProvider(baseUrl: string) {
  Object.assign(form, {
    base_url: baseUrl,
    model_id: baseUrl === SILICONFLOW_BASE_URL ? "BAAI/bge-m3" : "embedding-3",
    dimensions: 1024,
    api_key: "",
  });
  formRef.value?.clearValidate();
}

async function loadConfig() {
  loading.value = true;
  loadFailed.value = true;
  try {
    const response = await EmbeddingAPI.getConfig();
    if (response.data.code === 0) {
      const config = response.data.data;
      Object.assign(form, {
        base_url: config.base_url,
        model_id: config.model_id,
        dimensions: config.dimensions,
        api_key: "",
      });
      hasApiKey.value = config.has_api_key;
      savedBaseUrl.value = config.base_url;
      loadFailed.value = false;
    }
  } catch {
    /* 请求层统一展示错误。 */
  } finally {
    loading.value = false;
  }
}

async function testConnection() {
  if (!(await formRef.value?.validate().catch(() => false))) return;
  testing.value = true;
  testResult.value = null;
  try {
    const response = await EmbeddingAPI.testConfig({ ...form });
    if (response.data.code === 0) testResult.value = response.data.data;
  } catch {
    /* 请求层统一展示错误。 */
  } finally {
    testing.value = false;
  }
}

async function save() {
  if (!(await formRef.value?.validate().catch(() => false))) return;
  saving.value = true;
  try {
    const response = await EmbeddingAPI.saveConfig({ ...form });
    if (response.data.code === 0) {
      hasApiKey.value = response.data.data.has_api_key;
      savedBaseUrl.value = response.data.data.base_url;
      form.api_key = "";
    }
  } catch {
    /* 请求层统一展示错误。 */
  } finally {
    saving.value = false;
  }
}

onMounted(loadConfig);
</script>

<style scoped lang="scss">
.embedding-config {
  max-width: 640px;
  padding: 8px 0;
}

.embedding-heading {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.embedding-heading h3 {
  margin: 0 0 8px;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.embedding-heading p,
.embedding-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}

.embedding-form {
  margin-top: 24px;
}

.embedding-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.embedding-hint {
  margin-bottom: 20px;
}

.embedding-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}
@media (width <= 480px) {
  .embedding-options {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
