<script setup lang="ts">
import { computed, ref } from 'vue';
import MarkdownIt from 'markdown-it';
import {
  RobotOutlined,
  LoadingOutlined,
  WarningOutlined,
  DownOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue';

export interface SourceSummary {
  index: number;
  filename: string;
  chunk_index: number;
  summary: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thoughtContent?: string;
  answerContent?: string;
  status?: 'loading' | 'done' | 'error';
  progressText?: string;
  timestamp?: Date;
  sources?: SourceSummary[];
}

const props = defineProps<{
  message: Message;
}>();

const markdown = new MarkdownIt({
  breaks: true,
  linkify: true,
  html: false
});

const isUser = computed(() => props.message.role === 'user');
const isLoading = computed(() => props.message.status === 'loading');
const isError = computed(() => props.message.status === 'error');
const loadingText = computed(
  () => props.message.progressText || '正在处理中...'
);
const assistantThought = computed(
  () => props.message.thoughtContent?.trim() || ''
);
const assistantAnswer = computed(
  () => props.message.answerContent?.trim() || props.message.content.trim()
);
const hasThoughtSection = computed(
  () => props.message.role === 'assistant' && assistantThought.value.length > 0
);
const hasAnswerSection = computed(
  () => props.message.role === 'assistant' && assistantAnswer.value.length > 0
);
const hasSources = computed(
  () =>
    props.message.role === 'assistant' &&
    (props.message.sources?.length || 0) > 0
);
const isNoResult = computed(
  () =>
    props.message.role === 'assistant' &&
    (assistantAnswer.value.includes('知识库中没有找到') ||
      assistantAnswer.value.includes('知识库为空') ||
      assistantAnswer.value.includes('未找到'))
);
const thoughtExpanded = ref(false);

const renderedContent = computed(() => {
  if (!props.message.content) return '';
  return markdown.render(props.message.content);
});

const renderedThought = computed(() => {
  if (!assistantThought.value) return '';
  return markdown.render(assistantThought.value);
});

const renderedAnswer = computed(() => {
  if (!assistantAnswer.value) return '';
  return markdown.render(assistantAnswer.value);
});

const formattedTime = computed(() => {
  const ts = props.message.timestamp;
  if (!ts) return '';
  return ts.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
});

function toggleThought() {
  thoughtExpanded.value = !thoughtExpanded.value;
}
</script>

<template>
  <div :class="['message-row', isUser ? 'user-row' : 'assistant-row']">
    <div
      :class="[
        'message-shell',
        isUser ? 'user-shell' : 'assistant-shell',
        isError ? 'error-shell' : '',
        isNoResult ? 'no-result-shell' : ''
      ]">
      <div v-if="!isUser" class="message-head">
        <div class="agent-badge">
          <RobotOutlined v-if="!isLoading" class="agent-icon" />
          <LoadingOutlined v-else class="agent-icon spin" />
          <span>RAG.Agent</span>
        </div>
        <span v-if="formattedTime" class="msg-time">{{ formattedTime }}</span>
      </div>

      <template v-if="isLoading && !message.content && !hasThoughtSection">
        <div class="loading-block">
          <div class="loading-copy">{{ loadingText }}</div>
          <div class="skeleton-line w-92" />
          <div class="skeleton-line w-84" />
          <div class="skeleton-line w-60" />
        </div>
      </template>

      <template v-else-if="isNoResult">
        <div class="notice-block">
          <WarningOutlined class="notice-icon" />
          <div class="notice-copy markdown-body" v-html="renderedAnswer" />
        </div>
      </template>

      <template v-else>
        <div v-if="!isUser && hasThoughtSection" class="thought-wrap">
          <button class="thought-toggle" type="button" @click="toggleThought">
            <span class="thought-label">检索思路</span>
            <span class="thought-meta">
              {{ thoughtExpanded ? '收起' : '展开' }}
            </span>
            <DownOutlined
              :class="['thought-arrow', thoughtExpanded ? 'expanded' : '']" />
          </button>
          <div
            v-if="thoughtExpanded"
            class="thought-panel markdown-body"
            v-html="renderedThought" />
        </div>

        <section v-if="!isUser && hasAnswerSection" class="answer-wrap">
          <div class="section-kicker">答案</div>
          <div class="markdown-body answer-body" v-html="renderedAnswer" />
        </section>

        <div
          v-else-if="!isUser"
          class="markdown-body answer-body"
          v-html="renderedContent" />

        <div v-else class="user-text">{{ message.content }}</div>

        <section v-if="hasSources" class="sources-wrap">
          <div class="section-kicker">引用摘要</div>
          <div class="source-list">
            <article
              v-for="source in message.sources"
              :key="`${message.id}-${source.index}`"
              class="source-card">
              <div class="source-title-row">
                <div class="source-title">
                  <FileTextOutlined class="source-icon" />
                  <span>{{ source.filename }}</span>
                </div>
                <span class="source-tag">
                  片段 {{ source.chunk_index + 1 }}
                </span>
              </div>
              <p class="source-summary">{{ source.summary }}</p>
            </article>
          </div>
        </section>
      </template>

      <div v-if="isLoading && !isUser" class="status-line">
        {{ loadingText }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-row {
  display: flex;
  width: 100%;
  margin-bottom: 28px;
  animation: fadeIn 0.32s ease-out;
}

.user-row {
  justify-content: flex-end;
}

.assistant-row {
  justify-content: flex-start;
}

.message-shell {
  width: 100%;
  max-width: 100%;
}

.user-shell {
  max-width: min(78%, 640px);
  background: #18181b;
  color: #ffffff;
  border-radius: 24px 24px 8px 24px;
  padding: 16px 18px;
  box-shadow: 0 12px 32px rgba(24, 24, 27, 0.12);
}

.assistant-shell {
  max-width: min(100%, 760px);
}

.message-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(24, 24, 27, 0.06);
  border-radius: 999px;
  padding: 6px 10px;
  color: #27272a;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.agent-icon {
  color: #18181b;
}

.msg-time {
  color: #a1a1aa;
  font-size: 12px;
}

.loading-block,
.answer-wrap,
.thought-wrap,
.sources-wrap,
.notice-block,
.status-line,
.assistant-shell > .answer-body {
  margin-left: 8px;
}

.loading-copy,
.status-line {
  font-size: 13px;
  color: #71717a;
}

.loading-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-line {
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(90deg, #f4f4f5 0%, #e4e4e7 50%, #f4f4f5 100%);
  background-size: 200% 100%;
  animation: shimmer 1.3s linear infinite;
}

.w-92 {
  width: 92%;
}
.w-84 {
  width: 84%;
}
.w-60 {
  width: 60%;
}

.thought-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: #f5f5f5;
  color: #3f3f46;
  border-radius: 14px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.thought-toggle:hover {
  background: #ededed;
}

.thought-label,
.thought-meta {
  font-size: 12px;
  font-weight: 600;
}

.thought-meta {
  margin-left: auto;
  color: #71717a;
}

.thought-arrow {
  font-size: 12px;
  transition: transform 0.2s ease;
}

.thought-arrow.expanded {
  transform: rotate(180deg);
}

.thought-panel {
  margin-top: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #fafafa;
  border: 1px solid #ededed;
  color: #71717a;
}

.answer-wrap {
  margin-top: 16px;
  padding: 18px 20px;
  background: #ffffff;
  border: 1px solid rgba(24, 24, 27, 0.06);
  border-radius: 20px;
  box-shadow: 0 10px 30px rgba(24, 24, 27, 0.04);
}

.section-kicker {
  margin-bottom: 10px;
  color: #a1a1aa;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sources-wrap {
  margin-top: 14px;
}

.source-list {
  display: grid;
  gap: 10px;
}

.source-card {
  background: #ffffff;
  border: 1px solid rgba(24, 24, 27, 0.06);
  border-radius: 16px;
  padding: 14px 16px;
}

.source-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.source-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #18181b;
  font-size: 13px;
  font-weight: 600;
}

.source-icon {
  color: #71717a;
}

.source-tag {
  color: #71717a;
  font-size: 11px;
  white-space: nowrap;
}

.source-summary {
  margin: 10px 0 0;
  color: #52525b;
  line-height: 1.7;
  font-size: 13px;
}

.notice-block {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.notice-icon {
  color: #d97706;
  margin-top: 2px;
}

.notice-copy {
  color: #92400e;
}

.error-shell .answer-wrap,
.error-shell > .answer-body {
  border-color: #fecaca;
  background: #fef2f2;
}

.user-text {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 15px;
}

.markdown-body {
  font-size: 15px;
  line-height: 1.78;
  color: #18181b;
  word-break: break-word;
}

.answer-body :deep(p),
.thought-panel :deep(p),
.notice-copy :deep(p) {
  margin: 0 0 10px;
}

.answer-body :deep(p:last-child),
.thought-panel :deep(p:last-child),
.notice-copy :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 22px;
  margin: 10px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 6px;
}

.markdown-body :deep(code) {
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 13px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-body :deep(pre) {
  background: #18181b;
  color: #f4f4f5;
  padding: 16px;
  border-radius: 14px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #d4d4d8;
  padding-left: 14px;
  margin: 12px 0;
  color: #71717a;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 18px 0 10px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 640px) {
  .user-shell {
    max-width: 88%;
  }

  .answer-wrap,
  .thought-wrap,
  .sources-wrap,
  .notice-block,
  .status-line,
  .assistant-shell > .answer-body,
  .loading-block {
    margin-left: 0;
  }

  .source-title-row,
  .message-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
