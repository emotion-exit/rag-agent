<script setup lang="ts">
defineOptions({
  name: 'ChatView'
});

import { nextTick, reactive, ref } from 'vue';
import { v4 as uuidv4 } from 'uuid';
import {
  SendOutlined,
  ClearOutlined,
  RobotOutlined,
  VerticalAlignBottomOutlined
} from '@ant-design/icons-vue';
import AnswerCard from '@/components/AnswerCard.vue';
import SourceSnippetModal from '@/components/SourceSnippetModal.vue';
import { OButton, OCard } from '@/orange-ui';
import type {
  ClarificationOption,
  Message,
  SourceSummary
} from '@/components/AnswerCard.vue';
import { getApiBase } from '@/services/runtime';
import { buildPublicConfigHeaders } from '@/services/publicConfig';

const messages = ref<Message[]>([]);
const inputText = ref('');
const isLoading = ref(false);
const sessionId = ref(uuidv4());
const messagesContainer = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLTextAreaElement | null>(null);
const shouldAutoScroll = ref(true);
const showScrollBack = ref(false);
const selectedSource = ref<SourceSummary | null>(null);
const sourceModalVisible = ref(false);

const API_BASE = getApiBase();
const CONNECTING_HINT = '正在连接知识库助手...';
const START_HINT = '已接收问题，正在准备检索。';
const GENERATING_HINT = '正在生成回答...';

interface StreamEventPayload {
  type: string;
  content: string;
  sources?: SourceSummary[];
  options?: ClarificationOption[];
}

interface RetrievalFilters {
  knowledge_space: string;
  category: string;
}

const retrievalFilters = reactive<RetrievalFilters>({
  knowledge_space: '',
  category: ''
});

function buildRetrievalFiltersPayload() {
  const payload = {
    knowledge_space: retrievalFilters.knowledge_space.trim(),
    category: retrievalFilters.category.trim()
  };

  return Object.values(payload).some(Boolean) ? payload : undefined;
}

function pushProgressStep(message: Message, step: string) {
  const normalized = step.trim();
  if (!normalized) return;

  const nextSteps = [...(message.progressSteps || [])];
  if (nextSteps[nextSteps.length - 1] === normalized) {
    message.progressText = normalized;
    return;
  }

  if (!nextSteps.includes(normalized)) {
    nextSteps.push(normalized);
  }

  message.progressSteps = nextSteps;
  message.progressText = normalized;
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
        sources: Array.isArray(parsed.sources) ? parsed.sources : undefined,
        options: Array.isArray(parsed.options) ? parsed.options : undefined
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
    pushProgressStep(assistantMsg, data.content || START_HINT);
    scrollToBottom();
    return;
  }

  if (data.type === 'sources') {
    assistantMsg.sources = data.sources || [];
    return;
  }

  if (data.type === 'clarify') {
    assistantMsg.answerContent = data.content;
    assistantMsg.content = data.content;
    assistantMsg.clarificationOptions = Array.isArray(data.options)
      ? data.options
      : [];
    assistantMsg.status = 'done';
    assistantMsg.progressText = undefined;
    scrollToBottom(true);
    return;
  }

  if (data.type === 'progress' || data.type === 'retrieval') {
    assistantMsg.status = 'loading';
    pushProgressStep(assistantMsg, data.content);
    return;
  }

  if (data.type === 'text') {
    assistantMsg.answerContent =
      (assistantMsg.answerContent || '') + data.content;
    assistantMsg.content = assistantMsg.answerContent;
    assistantMsg.status = 'loading';
    pushProgressStep(assistantMsg, GENERATING_HINT);
    scrollToBottom();
    return;
  }

  if (data.type === 'thought') {
    assistantMsg.thoughtContent =
      (assistantMsg.thoughtContent || '') + data.content;
    assistantMsg.status = 'loading';
    scrollToBottom();
    return;
  }

  if (data.type === 'answer') {
    assistantMsg.answerContent =
      (assistantMsg.answerContent || '') + data.content;
    assistantMsg.content = assistantMsg.answerContent;
    assistantMsg.status = 'loading';
    pushProgressStep(assistantMsg, GENERATING_HINT);
    scrollToBottom();
    return;
  }

  if (data.type === 'done') {
    assistantMsg.status = 'done';
    pushProgressStep(assistantMsg, '回答已生成完成。');
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

  await submitMessage(text);
}

async function submitMessage(text: string) {
  if (!text.trim() || isLoading.value) return;

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
  if (inputText.value.trim() === text.trim()) {
    inputText.value = '';
  }
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
    clarificationOptions: [],
    status: 'loading',
    progressSteps: [],
    progressText: CONNECTING_HINT,
    timestamp: new Date()
  });
  messages.value.push(assistantMsg);
  scrollToBottom(true);

  try {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildPublicConfigHeaders()
      },
      body: JSON.stringify({
        message: text,
        session_id: sessionId.value,
        retrieval_filters: buildRetrievalFiltersPayload()
      })
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

async function applyClarificationOption(
  message: Message,
  option: ClarificationOption
) {
  if (isLoading.value) return;

  retrievalFilters[option.field] = option.value;
  const queryText = message.queryText?.trim();
  if (!queryText) return;

  await submitMessage(queryText);
}

function clearMessages() {
  messages.value = [];
  sessionId.value = uuidv4();
  shouldAutoScroll.value = true;
  showScrollBack.value = false;
}

function openSourceModal(source: SourceSummary) {
  selectedSource.value = source;
  sourceModalVisible.value = true;
}

function closeSourceModal() {
  sourceModalVisible.value = false;
  selectedSource.value = null;
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}
</script>

<template>
  <div class="relative flex min-h-0 flex-1 flex-col pt-0">
    <div
      class="flex min-h-0 flex-1 flex-col overflow-y-auto px-2 pb-5 pt-6 [scrollbar-color:rgba(113,113,122,0.45)_transparent] [scrollbar-width:thin] max-sm:px-0 max-sm:pb-4.5 max-sm:pt-5"
      ref="messagesContainer"
      @scroll="handleMessagesScroll">
      <div
        v-if="messages.length === 0"
        class="flex flex-1 animate-o-fade-in flex-col items-center justify-center text-center">
        <div class="mb-3 flex flex-col items-center gap-4">
          <div
            class="rounded-full bg-(--oui-color-primary-soft) p-5 text-[46px] text-(--oui-color-heading)">
            <RobotOutlined />
          </div>
          <h2
            class="m-0 text-2xl font-bold leading-tight tracking-tight text-(--oui-color-heading) max-sm:text-xl">
            有什么我可以帮您的？
          </h2>
        </div>
        <p class="mb-8 text-sm leading-relaxed text-(--oui-color-text-muted)">
          基于您的私有知识库直接作答；范围不明确时会先向您确认。
        </p>
        <div class="grid w-full max-w-140 gap-3">
          <OCard
            padding="md"
            html-class="grid grid-cols-[48px_1fr] items-start gap-4 text-left transition-all duration-200 hover:shadow-floating max-sm:grid-cols-[40px_1fr] max-sm:gap-3">
            <span
              class="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-(--oui-color-primary) text-sm font-bold text-white shadow-sm max-sm:h-10 max-sm:w-10">
              01
            </span>
            <div>
              <strong
                class="mb-1.5 block text-sm font-semibold text-(--oui-color-heading)">
                上传资料
              </strong>
              <p
                class="m-0 text-xs leading-relaxed text-(--oui-color-text-muted)">
                先在知识库页面导入 PDF、Markdown 或文档资料。
              </p>
            </div>
          </OCard>
          <OCard
            padding="md"
            html-class="grid grid-cols-[48px_1fr] items-start gap-4 text-left transition-all duration-200 hover:shadow-floating max-sm:grid-cols-[40px_1fr] max-sm:gap-3">
            <span
              class="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-(--oui-color-primary) text-sm font-bold text-white shadow-sm max-sm:h-10 max-sm:w-10">
              02
            </span>
            <div>
              <strong
                class="mb-1.5 block text-sm font-semibold text-(--oui-color-heading)">
                直接提问
              </strong>
              <p
                class="m-0 text-xs leading-relaxed text-(--oui-color-text-muted)">
                我会优先返回结论；命中范围不明确时先请您选择知识空间或分类。
              </p>
            </div>
          </OCard>
        </div>
      </div>

      <div v-else class="mt-auto flex w-full flex-col box-border pt-21">
        <template v-for="msg in messages" :key="msg.id">
          <AnswerCard
            :message="msg"
            @apply-clarification="applyClarificationOption(msg, $event)"
            @select-source="openSourceModal" />
        </template>
      </div>
    </div>

    <SourceSnippetModal
      :visible="sourceModalVisible"
      :source="selectedSource"
      :query-text="selectedSource?.summary || selectedSource?.filename || ''"
      @close="closeSourceModal" />

    <OButton
      v-if="showScrollBack"
      html-class="absolute right-6 bottom-30 z-10 rounded-full shadow-floating max-sm:right-3 max-sm:bottom-27"
      @click="scrollToBottom(true)">
      <VerticalAlignBottomOutlined />
      查看最新消息
    </OButton>

    <div class="bg-transparent pb-5">
      <div
        class="grid grid-cols-[auto_1fr_auto] items-end gap-2.5 rounded-3xl border border-black/8 bg-white/95 px-3 py-2.5 shadow-[0_8px_32px_rgba(24,24,27,0.08)] backdrop-blur-xl transition-all duration-200 focus-within:border-black/20 focus-within:shadow-[0_12px_48px_rgba(24,24,27,0.12)]">
        <OButton
          variant="ghost"
          size="sm"
          html-class="h-10 w-10 rounded-full p-0 transition-all duration-200 hover:bg-(--oui-color-danger-soft) hover:text-(--oui-color-danger)"
          title="清空对话"
          @click="clearMessages">
          <ClearOutlined />
        </OButton>
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="min-h-10 max-h-45 w-full resize-none border-0 bg-transparent px-1 py-2 text-sm leading-relaxed text-(--oui-color-heading) outline-none placeholder:text-(--oui-color-text-subtle) disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="给 RAG Agent 发送消息..."
          :disabled="isLoading"
          rows="1"
          @input="resizeTextarea"
          @keydown="handleKeyDown" />
        <OButton
          size="sm"
          html-class="h-10 w-10 rounded-full p-0 transition-all duration-200"
          :disabled="isLoading || !inputText.trim()"
          @click="sendMessage">
          <SendOutlined />
        </OButton>
      </div>
      <div
        class="mt-3 text-center text-xs leading-relaxed text-(--oui-color-text-subtle)">
        内容基于知识库生成，请结合原文核实结论。
      </div>
    </div>
  </div>
</template>
