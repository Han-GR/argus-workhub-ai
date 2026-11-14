<template>
  <div class="question-page" :aria-busy="asking">
    <header class="page-heading">
      <span class="eyebrow">团队知识库 / 问答</span>
      <h1>知识问答</h1>
      <p>从你有权访问的团队资料中查找答案，并核对引用来源。</p>
    </header>
    <section class="answer-panel" aria-labelledby="question-title">
      <div class="section-heading">
        <h3 id="question-title">向团队知识提问</h3>
        <span class="source-badge">回答附引用来源</span>
      </div>
      <p class="hint">描述具体问题，获得基于团队资料的回答。</p>
      <ElInput
        v-model="question"
        type="textarea"
        :rows="5"
        maxlength="1000"
        show-word-limit
        aria-label="知识库问题"
        placeholder="例如：员工年假有哪些规定？"
        :disabled="asking"
      />
      <div class="question-actions">
        <span class="hint scope-note"><Lock aria-hidden="true" />仅检索全公司与本部门可见资料</span>
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
    </section>
    <section v-if="!askError" class="result-panel" aria-label="问答结果" aria-live="polite">
      <div v-if="asking" class="answer-placeholder" role="status">
        <div class="result-icon"><Reading aria-hidden="true" /></div>
        <h3>正在查找资料并整理回答…</h3>
        <p>答案会附上可核对的引用来源。</p>
      </div>
      <div v-else-if="answer" class="answer-result" aria-live="polite">
        <h3>回答</h3>
        <p class="answer-text">{{ answer.answer }}</p>
        <h3 v-if="answer.sources.length">引用来源</h3>
        <article v-for="source in answer.sources" :key="source.number" class="source-card">
          <h4>[{{ source.number }}] {{ source.name }}</h4>
          <p>{{ source.text }}</p>
        </article>
      </div>
      <div v-else-if="!asking && !askError" class="answer-placeholder">
        <div class="result-icon"><Reading aria-hidden="true" /></div>
        <h3>让团队知识，成为你的答案</h3>
        <p>在上方提出问题，回答与引用将在这里展示。</p>
        <small>例如：请假流程怎么走？项目交付需要哪些材料？</small>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { Lock, Reading } from "@element-plus/icons-vue";
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
  padding: 28px;
  margin: 0 auto;
  color: var(--el-text-color-primary);
}
.page-heading {
  margin-bottom: 28px;
}
.page-heading h1 {
  margin: 8px 0;
  font-size: 26px;
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
  letter-spacing: 1px;
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
.answer-panel,
.result-panel {
  padding: 28px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
}
.result-panel {
  margin-top: 20px;
}
.answer-panel > .hint {
  margin: -4px 0 20px;
}
.source-badge {
  padding: 5px 10px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-radius: 6px;
  font-size: 12px;
}
:deep(.el-textarea__inner) {
  padding: 16px 18px 28px;
  line-height: 1.8;
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
  box-shadow: 0 0 0 1px var(--el-border-color-lighter) inset;
}
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}
:deep(.el-input__count) {
  right: 14px;
  bottom: 8px;
  background: transparent;
}
.question-actions {
  margin: 20px 0 0;
}
.question-actions :deep(.el-button) {
  min-width: 100px;
  height: 40px;
}
.scope-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.scope-note svg {
  flex: 0 0 14px;
  width: 14px;
}
.answer-placeholder {
  padding: 28px 12px 36px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.result-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  margin: 0 auto 16px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-radius: 16px;
}
.result-icon svg {
  width: 26px;
  height: 26px;
}
.answer-placeholder h3 {
  margin: 0 0 8px;
  color: var(--el-text-color-primary);
  font-size: 17px;
  font-weight: 600;
}
.answer-placeholder p {
  margin: 0 0 8px;
}
.answer-placeholder small {
  font-size: 12px;
}
.answer-text,
.source-card p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.9;
}
.answer-result {
  margin-top: 0;
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
  .answer-panel,
  .result-panel {
    padding: 20px 16px;
  }
}
</style>
