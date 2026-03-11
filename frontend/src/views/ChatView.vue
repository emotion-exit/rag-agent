<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue';
import { v4 as uuidv4 } from 'uuid';
import {
  SendOutlined,
  ClearOutlined,
  RobotOutlined,
  VerticalAlignBottomOutlined
} from '@ant-design/icons-vue';
import AnswerCard from '@/components/AnswerCard.vue';
import type { Message, SourceSummary } from '@/components/AnswerCard.vue';

const messages = ref<Message[]>([]);
const inputText = ref('');
const isLoading = ref(false);
const sessionId = ref(uuidv4());
const messagesContainer = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLTextAreaElement | null>(null);
const shouldAutoScroll = ref(true);
const showScrollBack = ref(false);

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const CONNECTING_HINT = '正在连接知识库助手...';
const START_HINT = '已建立流连接，开始检索相关资料...';
const THINKING_HINT = '正在整理答案...';
const GENERATING_HINT = '正在生成回答...';

interface StreamEventPayload {
  type: string;
  content: string;
  sources?: SourceSummary[];
}

function parseStreamEventBlock(block: string): StreamEventPayload | null {
  const dataLines = block
    .replace(/\r/g, '')
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (dataLines.length === 0) {
    return null;
  }

  const payload = dataLines.join('\n');

  try {
    const parsed = JSON.parse(payload);

    if (typeof parsed === 'string') {
      return { type: 'text', content: parsed };
    }

    if (parsed && typeof parsed === 'object' && 'type' in parsed) {
      return {
        type: String(parsed.type),
        content:
          typeof parsed.content === 'string'
            ? parsed.content
            : JSON.stringify(parsed.content),
        sources: Array.isArray(parsed.sources) ? parsed.sources : undefined
      };
    }
  } catch {
    return { type: 'text', content: payload };
  }

  return null;
}

function syncAutoScrollState() {
  const container = messagesContainer.value;
  if (!container) return;

  const distanceFromBottom =
    container.scrollHeight - container.scrollTop - container.clientHeight;
  const nearBottom = distanceFromBottom < 80;

  shouldAutoScroll.value = nearBottom;
  showScrollBack.value = !nearBottom;
}

function handleMessagesScroll() {
  syncAutoScrollState();
}

function scrollToBottom(force = false) {
  nextTick(() => {
    const container = messagesContainer.value;
    if (!container) return;
    if (!force && !shouldAutoScroll.value) return;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth'
    });
    shouldAutoScroll.value = true;
    showScrollBack.value = false;
  });
}

function resetTextareaHeight() {
  const textarea = inputRef.value;
  if (!textarea) return;
  textarea.style.height = 'auto';
}

function resizeTextarea() {
  const textarea = inputRef.value;
  if (!textarea) return;
  textarea.style.height = 'auto';
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
}

function applyStreamEvent(assistantMsg: Message, data: StreamEventPayload) {
  if (data.type === 'start') {
    if (!assistantMsg.content) {
      assistantMsg.progressText = START_HINT;
      scrollToBottom();
    }
    return;
  }

  if (data.type === 'sources') {
    assistantMsg.sources = data.sources || [];
    return;
  }

  if (data.type === 'retrieval') {
    assistantMsg.status = 'loading';
    assistantMsg.progressText = data.content;
    return;
  }

  if (data.type === 'text') {
    assistantMsg.answerContent =
      (assistantMsg.answerContent || '') + data.content;
    assistantMsg.content = assistantMsg.answerContent;
    assistantMsg.status = 'loading';
    assistantMsg.progressText = GENERATING_HINT;
    scrollToBottom();
    return;
  }

  if (data.type === 'thought') {
    assistantMsg.thoughtContent =
      (assistantMsg.thoughtContent || '') + data.content;
    assistantMsg.status = 'loading';
    assistantMsg.progressText = THINKING_HINT;
    return;
  }

  if (data.type === 'answer') {
    assistantMsg.answerContent =
      (assistantMsg.answerContent || '') + data.content;
    assistantMsg.content = assistantMsg.answerContent;
    assistantMsg.status = 'loading';
    assistantMsg.progressText = GENERATING_HINT;
    scrollToBottom();
    return;
  }

  if (data.type === 'done') {
    assistantMsg.status = 'done';
    assistantMsg.progressText = undefined;
    scrollToBottom();
    return;
  }

  if (data.type === 'error') {
    assistantMsg.content = `请求失败：${data.content}\n\n请检查后端服务是否正常运行。`;
    assistantMsg.status = 'error';
    assistantMsg.progressText = undefined;
    scrollToBottom(true);
  }
}

async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || isLoading.value) return;

  shouldAutoScroll.value = true;
  showScrollBack.value = false;

  const userMsg: Message = {
    id: uuidv4(),
    role: 'user',
    content: text,
    status: 'done',
    timestamp: new Date()
  };
  messages.value.push(userMsg);
  inputText.value = '';
  resetTextareaHeight();
  isLoading.value = true;
  scrollToBottom(true);

  const assistantMsg = reactive<Message>({
    id: uuidv4(),
    role: 'assistant',
    content: '',
    thoughtContent: '',
    answerContent: '',
    queryText: text,
    sources: [],
    status: 'loading',
    progressText: CONNECTING_HINT,
    timestamp: new Date()
  });
  messages.value.push(assistantMsg);
  scrollToBottom(true);

  try {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId.value })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) throw new Error('No response body');

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const normalizedBuffer = buffer
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n');
      const eventBlocks = normalizedBuffer.split('\n\n');
      buffer = eventBlocks.pop() || '';

      for (const eventBlock of eventBlocks) {
        const data = parseStreamEventBlock(eventBlock);
        if (data) {
          applyStreamEvent(assistantMsg, data);
        }
      }
    }

    const trailingEvent = parseStreamEventBlock(buffer);
    if (trailingEvent) {
      applyStreamEvent(assistantMsg, trailingEvent);
    }

    assistantMsg.status = 'done';
    assistantMsg.progressText = undefined;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    assistantMsg.content = `请求失败：${errorMsg}\n\n请检查后端服务是否正常运行。`;
    assistantMsg.status = 'error';
    assistantMsg.progressText = undefined;
    scrollToBottom(true);
  } finally {
    isLoading.value = false;
  }
}

function clearMessages() {
  messages.value = [];
  sessionId.value = uuidv4();
  shouldAutoScroll.value = true;
  showScrollBack.value = false;
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}
</script>

<template>
  <div class="chat-container">
    <div
      class="messages-area"
      ref="messagesContainer"
      @scroll="handleMessagesScroll">
      <div v-if="messages.length === 0" class="welcome-container">
        <div class="welcome-heading">
          <RobotOutlined class="welcome-icon" />
          <h2>有什么我可以帮您的？</h2>
        </div>
        <p class="welcome-subtitle">
          基于您的私有知识库，直接给出简洁答案与引用摘要。
        </p>
        <div class="suggestions">
          <div class="suggestion-item">
            <span>01</span>
            <div>
              <strong>上传资料</strong>
              <p>先在知识库页面导入 PDF、Markdown 或文档资料。</p>
            </div>
          </div>
          <div class="suggestion-item">
            <span>02</span>
            <div>
              <strong>直接提问</strong>
              <p>我会优先返回结论，再附上可阅读的引用摘要。</p>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="messages-stack">
        <template v-for="msg in messages" :key="msg.id">
          <AnswerCard :message="msg" />
        </template>
      </div>
    </div>

    <button
      v-if="showScrollBack"
      class="scroll-back-btn"
      type="button"
      @click="scrollToBottom(true)">
      <VerticalAlignBottomOutlined />
      查看最新消息
    </button>

    <div class="input-container">
      <div class="input-wrapper">
        <button
          class="icon-btn danger-btn"
          type="button"
          title="清空对话"
          @click="clearMessages">
          <ClearOutlined />
        </button>
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="给 RAG Agent 发送消息..."
          :disabled="isLoading"
          rows="1"
          @input="resizeTextarea"
          @keydown="handleKeyDown" />
        <button
          class="send-btn"
          type="button"
          :disabled="isLoading || !inputText.trim()"
          @click="sendMessage">
          <SendOutlined />
        </button>
      </div>
      <div class="input-footer">内容基于知识库生成，请结合原文核实结论。</div>
    </div>
  </div>
</template>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  position: relative;
  padding-top: 78px;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 42px 8px 20px;
  margin-top: -78px;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
  scrollbar-color: rgba(113, 113, 122, 0.45) transparent;
}

.messages-area::-webkit-scrollbar {
  width: 6px;
}

.messages-area::-webkit-scrollbar-track {
  background: transparent;
}

.messages-area::-webkit-scrollbar-thumb {
  background: rgba(113, 113, 122, 0.36);
  border-radius: 999px;
}

.messages-area::-webkit-scrollbar-thumb:hover {
  background: rgba(82, 82, 91, 0.56);
}

.messages-stack {
  display: flex;
  flex-direction: column;
  width: 100%;
  margin-top: auto;
  padding-top: 84px;
  box-sizing: border-box;
}

.welcome-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  flex: 1;
  text-align: center;
  animation: fadeIn 0.4s ease-out;
}

.welcome-heading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.welcome-icon {
  font-size: 46px;
  color: #1a1a1a;
  background: #f4f4f5;
  padding: 20px;
  border-radius: 50%;
}

.welcome-heading h2 {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: #1a1a1a;
}

.welcome-subtitle {
  margin: 0 0 36px;
  font-size: 15px;
  color: #71717a;
}

.suggestions {
  width: 100%;
  max-width: 560px;
  display: grid;
  gap: 14px;
}

.suggestion-item {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 16px;
  align-items: start;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(24, 24, 27, 0.06);
  border-radius: 22px;
  padding: 18px 20px;
  text-align: left;
}

.suggestion-item span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #18181b;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}

.suggestion-item strong {
  display: block;
  font-size: 15px;
  color: #18181b;
  margin-bottom: 4px;
}

.suggestion-item p {
  margin: 0;
  color: #71717a;
  font-size: 13px;
  line-height: 1.7;
}

.scroll-back-btn {
  position: absolute;
  right: 24px;
  bottom: 120px;
  z-index: 10;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 999px;
  background: #18181b;
  color: #ffffff;
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 16px 32px rgba(24, 24, 27, 0.16);
}

.input-container {
  padding: 0 0 20px;
  background: transparent;
}

.input-wrapper {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: end;
  gap: 10px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(24, 24, 27, 0.08);
  border-radius: 28px;
  padding: 10px 12px;
  box-shadow: 0 18px 42px rgba(24, 24, 27, 0.06);
}

.input-wrapper:focus-within {
  border-color: rgba(24, 24, 27, 0.18);
}

.icon-btn,
.send-btn {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.icon-btn {
  background: transparent;
  color: #71717a;
}

.icon-btn:hover {
  background: #f4f4f5;
  color: #18181b;
}

.danger-btn:hover {
  background: #fef2f2;
  color: #dc2626;
}

.chat-input {
  width: 100%;
  min-height: 40px;
  max-height: 180px;
  resize: none;
  border: 0;
  background: transparent;
  color: #18181b;
  font-size: 15px;
  line-height: 1.7;
  outline: none;
  padding: 8px 2px;
  font-family: inherit;
}

.chat-input::placeholder {
  color: #a1a1aa;
}

.send-btn {
  background: #18181b;
  color: #ffffff;
}

.send-btn:hover:not(:disabled) {
  background: #27272a;
}

.send-btn:disabled,
.icon-btn:disabled,
.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-footer {
  text-align: center;
  margin-top: 12px;
  color: #a1a1aa;
  font-size: 12px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .messages-area {
    padding: 20px 0 18px;
  }

  .welcome-heading h2 {
    font-size: 24px;
  }

  .suggestion-item {
    grid-template-columns: 40px 1fr;
    padding: 16px;
  }

  .suggestion-item span {
    width: 40px;
    height: 40px;
  }

  .scroll-back-btn {
    right: 12px;
    bottom: 108px;
  }
}
</style>
