<template>
  <div class="question-page" :aria-busy="asking">
    <header class="page-heading">
      <span class="eyebrow">KNOWLEDGE ANSWERS</span>
      <h1>知识问答</h1>
      <p>从你有权访问的团队资料中查找答案，并核对引用来源。</p>
    </header>
    <section class="answer-panel" aria-labelledby="question-title">
      <div class="section-heading">
        <h3 id="question-title">基于资料提问</h3>
        <span class="eyebrow">RAG</span>
      </div>
      <p class="hint">
        问答仅检索全公司和你当前部门的资料，聊天模型使用你的个人配置；索引失效的文档需由上传者重建。
      </p>
      <ElInput
        v-model="question"
        type="textarea"
        :rows="4"
        maxlength="1000"
        show-word-limit
        aria-label="知识库问题"
        placeholder="例如：员工年假有哪些规定？"
        :disabled="asking"
      />
      <div class="question-actions">
        <span class="hint">按当前账号权限检索</span>
        <ElButton
          type="primary"
          :loading="asking"
          :disabled="asking || !question.trim()"
          @click="ask"
          >提问</ElButton
        >
      </div>
      <ElAlert
        v-if="askError"
        title="提问失败，请检查模型配置或稍后重试。"
        type="error"
        :closable="false"
      />
      <div v-if="answer" class="answer-result" aria-live="polite">
        <h3>回答</h3>
        <p class="answer-text">{{ answer.answer }}</p>
        <h3 v-if="answer.sources.length">引用来源</h3>
        <article v-for="source in answer.sources" :key="source.number" class="source-card">
          <h4>[{{ source.number }}] {{ source.name }}</h4>
          <p>{{ source.text }}</p>
        </article>
      </div>
      <div v-else-if="!asking && !askError" class="answer-placeholder">
        <span class="eyebrow">从资料到答案</span>
        <p>回答与引用将在这里展示。</p>
        <small>资料不足时会明确说明，请结合原文核对回答。</small>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { ElAlert, ElButton, ElInput } from "element-plus";
import { KnowledgeAPI, type KnowledgeAnswer } from "@/api/module_ai/knowledge";
defineOptions({ name: "KnowledgeQuestion" });
const question = ref("");
const asking = ref(false);
const answer = ref<KnowledgeAnswer | null>(null);
const askError = ref(false);
async function ask() {
  const value = question.value.trim();
  if (!value || value.length > 1000 || asking.value) return;
  asking.value = true;
  answer.value = null;
  askError.value = false;
  try {
    const response = await KnowledgeAPI.ask(value);
    if (response.data.code !== 0) throw new Error("ask failed");
    answer.value = response.data.data;
  } catch {
    askError.value = true;
  } finally {
    asking.value = false;
  }
}
</script>
<style scoped lang="scss">
.question-page {
  max-width: 1100px;
  padding: 24px;
  margin: 0 auto;
  color: var(--el-text-color-primary);
}
.page-heading {
  margin-bottom: 28px;
}
.page-heading h1 {
  margin: 8px 0;
  font-size: 28px;
}
.page-heading p,
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.eyebrow {
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
}
.section-heading,
.question-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}
.section-heading {
  margin-bottom: 16px;
}
.section-heading h3,
.answer-result h3 {
  margin: 0;
  font-size: 16px;
}
.question-actions {
  margin: 16px 0 24px;
}
.answer-placeholder {
  padding: 40px 12px;
  margin-top: 32px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.8;
}
.answer-text,
.source-card p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.9;
}
.answer-result {
  margin-top: 28px;
}
.source-card {
  padding: 16px;
  margin-top: 12px;
  background: var(--el-fill-color-light);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 4px;
}
.source-card h4 {
  margin: 0 0 8px;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.source-card p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
@media (width <= 600px) {
  .question-page {
    padding: 12px;
  }
}
</style>
