<script setup lang="ts">
import { computed, ref } from 'vue';
import MarkdownIt from 'markdown-it';
import {
  RobotOutlined,
  LoadingOutlined,
  WarningOutlined,
  DownOutlined
} from '@ant-design/icons-vue';
import SourceSnippetModal from '@/components/SourceSnippetModal.vue';

export interface SourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  system_name: string;
  module_name: string;
  feature_name: string;
  version_name: string;
  doc_type: string;
  source_type: string;
  source_label: string;
  source_page: number;
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
  queryText?: string;
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
    props.message.status === 'done' &&
    (props.message.sources?.length || 0) > 0
);
const showStatusLine = computed(
  () =>
    props.message.role === 'assistant' &&
    props.message.status === 'loading' &&
    (Boolean(props.message.content) || hasThoughtSection.value)
);
const isNoResult = computed(
  () =>
    props.message.role === 'assistant' &&
    (assistantAnswer.value.includes('知识库中没有找到') ||
      assistantAnswer.value.includes('知识库为空') ||
      assistantAnswer.value.includes('未找到'))
);
const thoughtExpanded = ref(false);
const activeSource = ref<SourceSummary | null>(null);

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

async function openSource(source: SourceSummary) {
  activeSource.value = source;
}

function closeSourceModal() {
  activeSource.value = null;
}

function buildSourceMeta(source: SourceSummary) {
  const sourceTypeLabel =
    source.source_type === 'image_ocr' ? '截图识别' : '正文文本';

  return [
    sourceTypeLabel,
    source.system_name,
    source.module_name,
    source.version_name
  ]
    .map((item) => item?.trim())
    .filter(Boolean)
    .join(' / ');
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

        <div v-if="hasSources" class="sources-inline-wrap">
          <div class="sources-inline-label">参考来源:</div>
          <div class="source-badges">
            <button
              v-for="(source, index) in message.sources"
              :key="`${message.id}-${source.index}`"
              type="button"
              class="source-badge"
              :title="`查看原文片段: ${source.filename}`"
              @click="openSource(source)">
              <span class="source-badge-index">{{ index + 1 }}</span>
              <span class="source-badge-copy">
                <span class="source-filename">{{ source.filename }}</span>
                <span v-if="buildSourceMeta(source)" class="source-meta">
                  {{ buildSourceMeta(source) }}
                </span>
              </span>
            </button>
          </div>
        </div>
      </template>

      <div v-if="showStatusLine" class="status-line">
        {{ loadingText }}
      </div>
    </div>

    <SourceSnippetModal
      :visible="Boolean(activeSource)"
      :source="activeSource"
      :query-text="message.queryText"
      @close="closeSourceModal" />
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
  max-width: 100%;
}

.user-shell {
  width: fit-content;
  max-width: min(78%, 640px);
  background: #18181b;
  color: #ffffff;
  border-radius: 24px 24px 8px 24px;
  padding: 16px 18px;
  box-shadow: 0 12px 32px rgba(24, 24, 27, 0.12);
}

.assistant-shell {
  width: 100%;
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
.sources-inline-wrap,
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

.sources-inline-wrap {
  margin-top: 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid rgba(24, 24, 27, 0.08);
}

.sources-inline-label {
  font-size: 12px;
  font-weight: 600;
  color: #71717a;
  padding-top: 5px;
}

.source-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}

.source-badge {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 14px;
  padding: 4px 10px 4px 6px;
  font-size: 12px;
  color: #3f3f46;
  cursor: pointer;
  transition: all 0.2s ease;
}

.source-badge:hover {
  background: #e4e4e7;
  border-color: rgba(24, 24, 27, 0.1);
  color: #18181b;
}

.source-badge-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.source-badge-index {
  background: #ffffff;
  color: #1a1a1a;
  font-weight: 600;
  font-size: 10px;
  min-width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.source-filename {
  display: block;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-meta {
  color: #71717a;
  font-size: 11px;
  white-space: nowrap;
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
    width: fit-content;
    max-width: 88%;
  }

  .answer-wrap,
  .thought-wrap,
  .sources-inline-wrap,
  .notice-block,
  .status-line,
  .assistant-shell > .answer-body,
  .loading-block {
    margin-left: 0;
  }

  .message-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
