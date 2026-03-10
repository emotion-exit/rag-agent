<script setup lang="ts">
import { ref, nextTick, h } from 'vue'
import { v4 as uuidv4 } from 'uuid'
import { SendOutlined, ClearOutlined, RobotOutlined } from '@ant-design/icons-vue'
import AnswerCard from '@/components/AnswerCard.vue'
import type { Message } from '@/components/AnswerCard.vue'

const messages = ref<Message[]>([])
const inputText = ref('')
const isLoading = ref(false)
const sessionId = ref(uuidv4())
const messagesEndRef = ref<HTMLElement | null>(null)

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function scrollToBottom() {
  nextTick(() => {
    messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  const userMsg: Message = {
    id: uuidv4(),
    role: 'user',
    content: text,
    status: 'done',
    timestamp: new Date(),
  }
  messages.value.push(userMsg)
  inputText.value = ''
  isLoading.value = true
  scrollToBottom()

  const assistantMsg: Message = {
    id: uuidv4(),
    role: 'assistant',
    content: '',
    status: 'loading',
    timestamp: new Date(),
  }
  messages.value.push(assistantMsg)
  scrollToBottom()

  try {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId.value }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) throw new Error('No response body')

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'text') {
              assistantMsg.content += data.content
              assistantMsg.status = 'loading'
              scrollToBottom()
            } else if (data.type === 'done') {
              assistantMsg.status = 'done'
              scrollToBottom()
            } else if (data.type === 'error') {
              assistantMsg.content = `⚠️ 错误：${data.content}`
              assistantMsg.status = 'error'
              scrollToBottom()
            }
          } catch {
            // ignore parse errors
          }
        }
      }
    }
    assistantMsg.status = 'done'
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err)
    assistantMsg.content = `⚠️ 请求失败：${errorMsg}\n\n请检查后端服务是否正常运行。`
    assistantMsg.status = 'error'
    scrollToBottom()
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

function clearMessages() {
  messages.value = []
  sessionId.value = uuidv4()
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="chat-container">
    <a-card class="chat-card" :bordered="false">
      <!-- Header -->
      <template #title>
        <div class="chat-header">
          <RobotOutlined class="header-icon" />
          <span>智能知识库问答</span>
          <a-tag color="blue" style="margin-left: 8px; font-size: 11px">RAG Agent</a-tag>
        </div>
      </template>
      <template #extra>
        <a-tooltip title="清空对话">
          <a-button type="text" :icon="h(ClearOutlined)" @click="clearMessages" />
        </a-tooltip>
      </template>

      <!-- Message area -->
      <div class="messages-area">
        <!-- Welcome message -->
        <div v-if="messages.length === 0" class="welcome-container">
          <div class="welcome-card">
            <RobotOutlined class="welcome-icon" />
            <h2>欢迎使用 RAG Agent</h2>
            <p>我只会基于您上传的知识库内容来回答问题。</p>
            <p>如果知识库中没有相关内容，我会如实告知您。</p>
            <a-divider />
            <div class="tips">
              <a-tag color="green">📚 先去上传知识库文档</a-tag>
              <a-tag color="blue">💬 然后在这里提问</a-tag>
              <a-tag color="purple">✅ 获取精准的知识库答案</a-tag>
            </div>
          </div>
        </div>

        <!-- Messages -->
        <template v-for="msg in messages" :key="msg.id">
          <AnswerCard :message="msg" />
        </template>
        <div ref="messagesEndRef" />
      </div>

      <!-- Input area -->
      <div class="input-area">
        <a-textarea
          v-model:value="inputText"
          placeholder="输入您的问题，按 Enter 发送（Shift+Enter 换行）..."
          :auto-size="{ minRows: 2, maxRows: 5 }"
          :disabled="isLoading"
          @keydown="handleKeyDown"
          class="chat-input"
        />
        <a-button
          type="primary"
          :loading="isLoading"
          :disabled="!inputText.trim()"
          @click="sendMessage"
          class="send-btn"
          size="large"
        >
          <template #icon><SendOutlined /></template>
          发送
        </a-button>
      </div>
    </a-card>
  </div>
</template>

<style scoped>
.chat-container {
  height: calc(100vh - 96px);
  display: flex;
  flex-direction: column;
}

.chat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 16px !important;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08) !important;
  overflow: hidden;
  height: 100%;
}

.chat-card :deep(.ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.header-icon {
  font-size: 20px;
  color: #1890ff;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  background: #f8faff;
  scroll-behavior: smooth;
}

.welcome-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 300px;
}

.welcome-card {
  text-align: center;
  padding: 40px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  max-width: 480px;
}

.welcome-icon {
  font-size: 64px;
  color: #1890ff;
  margin-bottom: 16px;
  display: block;
}

.welcome-card h2 {
  font-size: 22px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 8px;
}

.welcome-card p {
  color: #595959;
  line-height: 1.6;
  margin-bottom: 6px;
}

.tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.input-area {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

.chat-input {
  flex: 1;
  border-radius: 10px !important;
}

.send-btn {
  border-radius: 10px !important;
  min-width: 88px;
}
</style>
