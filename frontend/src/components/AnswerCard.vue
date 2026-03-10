<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import {
  UserOutlined,
  RobotOutlined,
  LoadingOutlined,
  BookOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: 'loading' | 'done' | 'error'
  timestamp?: Date
}

const props = defineProps<{
  message: Message
}>()

const isUser = computed(() => props.message.role === 'user')
const isLoading = computed(() => props.message.status === 'loading')
const isError = computed(() => props.message.status === 'error')
const isNoResult = computed(
  () =>
    props.message.role === 'assistant' &&
    (props.message.content.includes('知识库中没有找到') ||
      props.message.content.includes('知识库为空') ||
      props.message.content.includes('未找到'))
)

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content) as string
})

const formattedTime = computed(() => {
  const ts = props.message.timestamp
  if (!ts) return ''
  return ts.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <div :class="['message-row', isUser ? 'user-row' : 'assistant-row']">
    <!-- Avatar -->
    <div v-if="!isUser" class="avatar assistant-avatar">
      <RobotOutlined v-if="!isLoading" />
      <LoadingOutlined v-else class="spin" />
    </div>

    <!-- Message card -->
    <a-card
      :class="[
        'message-card',
        isUser ? 'user-card' : 'assistant-card',
        isError ? 'error-card' : '',
        isNoResult ? 'no-result-card' : '',
      ]"
      :bordered="false"
      size="small"
    >
      <!-- Loading skeleton -->
      <template v-if="isLoading && !message.content">
        <a-skeleton :active="true" :paragraph="{ rows: 2 }" :title="false" />
      </template>

      <!-- No result indicator -->
      <template v-else-if="isNoResult">
        <div class="no-result-content">
          <WarningOutlined class="no-result-icon" />
          <div class="no-result-text" v-html="renderedContent" />
        </div>
      </template>

      <!-- Normal content -->
      <template v-else>
        <div
          v-if="!isUser"
          class="markdown-body"
          v-html="renderedContent"
        />
        <div v-else class="user-text">{{ message.content }}</div>
      </template>

      <!-- Footer -->
      <template #extra>
        <span v-if="formattedTime" class="msg-time">{{ formattedTime }}</span>
      </template>
    </a-card>

    <!-- User avatar -->
    <div v-if="isUser" class="avatar user-avatar">
      <UserOutlined />
    </div>
  </div>
</template>

<style scoped>
.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease;
}

.user-row {
  flex-direction: row-reverse;
}

.assistant-row {
  flex-direction: row;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 4px;
}

.user-avatar {
  background: linear-gradient(135deg, #1890ff, #096dd9);
  color: #fff;
}

.assistant-avatar {
  background: linear-gradient(135deg, #52c41a, #389e0d);
  color: #fff;
}

.message-card {
  max-width: 72%;
  min-width: 60px;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08) !important;
  transition: box-shadow 0.2s;
}

.message-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12) !important;
}

.user-card {
  background: linear-gradient(135deg, #1890ff, #096dd9) !important;
  color: #fff !important;
}

.user-card .user-text {
  color: #fff;
  line-height: 1.6;
}

.assistant-card {
  background: #fff !important;
}

.error-card {
  border-left: 3px solid #ff4d4f !important;
}

.no-result-card {
  background: #fffbe6 !important;
  border-left: 3px solid #faad14 !important;
}

.no-result-content {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.no-result-icon {
  font-size: 18px;
  color: #faad14;
  margin-top: 2px;
  flex-shrink: 0;
}

.no-result-text {
  color: #8c6d00;
  line-height: 1.6;
}

.msg-time {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.35);
}

.user-card .msg-time {
  color: rgba(255, 255, 255, 0.65);
}

.spin {
  animation: spin 1s linear infinite;
}

/* Markdown styling inside assistant cards */
.markdown-body {
  line-height: 1.7;
  color: #262626;
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.markdown-body :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #1890ff;
  padding-left: 12px;
  margin: 8px 0;
  color: #595959;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 12px 0 8px;
  font-weight: 600;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #f0f0f0;
  margin: 12px 0;
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
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
