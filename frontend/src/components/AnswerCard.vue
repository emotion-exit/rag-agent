<script setup lang="ts">
import { computed, ref } from 'vue';
import MarkdownIt from 'markdown-it';
import {
  RobotOutlined,
  LoadingOutlined,
  WarningOutlined,
  DownOutlined
} from '@ant-design/icons-vue';
import { cn } from '@/utils/cn';

export interface ClarificationOption {
  field: 'knowledge_space';
  value: string;
  label: string;
}

export interface SourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  knowledge_space: string;
  tags: string;
  source_type: string;
  source_label: string;
  source_page: number;
  image_count?: number;
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
  progressSteps?: string[];
  progressQueryVariants?: string[];
  timestamp?: Date;
  sources?: SourceSummary[];
  queryText?: string;
  clarificationOptions?: ClarificationOption[];
  knowledgeSpaceLabel?: string;
}

const props = defineProps<{
  message: Message;
}>();

const emit = defineEmits<{
  applyClarification: [option: ClarificationOption];
  selectSource: [source: SourceSummary];
}>();

const markdown = new MarkdownIt({
  breaks: true,
  linkify: false,
  html: false
});

markdown.renderer.rules.link_open = () => '';
markdown.renderer.rules.link_close = () => '';

const isUser = computed(() => props.message.role === 'user');
const isLoading = computed(() => props.message.status === 'loading');
const isError = computed(() => props.message.status === 'error');
const assistantAnswer = computed(
  () => props.message.answerContent?.trim() || props.message.content.trim()
);
const assistantThought = computed(
  () => props.message.thoughtContent?.trim() || ''
);
const progressSteps = computed(() => props.message.progressSteps || []);
const progressQueryVariants = computed(
  () => props.message.progressQueryVariants || []
);
const hasAnswerSection = computed(
  () => props.message.role === 'assistant' && assistantAnswer.value.length > 0
);
const hasThoughtSection = computed(
  () => props.message.role === 'assistant' && assistantThought.value.length > 0
);
const hasProgressSection = computed(
  () =>
    props.message.role === 'assistant' &&
    (progressSteps.value.length > 0 || progressQueryVariants.value.length > 1)
);
const isNoResult = computed(
  () =>
    props.message.role === 'assistant' &&
    (assistantAnswer.value.includes('知识库中没有找到') ||
      assistantAnswer.value.includes('知识库为空') ||
      assistantAnswer.value.includes('未找到'))
);
const clarificationOptions = computed(
  () => props.message.clarificationOptions || []
);
const hasClarification = computed(
  () =>
    props.message.role === 'assistant' && clarificationOptions.value.length > 0
);
const sourceItems = computed(() => props.message.sources || []);
const hasSources = computed(
  () => props.message.role === 'assistant' && sourceItems.value.length > 0
);
const knowledgeSpaceLabel = computed(
  () => props.message.knowledgeSpaceLabel?.trim() || ''
);
const hasKnowledgeSpaceLabel = computed(
  () =>
    props.message.role === 'assistant' && knowledgeSpaceLabel.value.length > 0
);

const renderedContent = computed(() => {
  if (!props.message.content) return '';
  return markdown.render(props.message.content);
});

const renderedAnswer = computed(() => {
  if (!assistantAnswer.value) return '';
  return markdown.render(assistantAnswer.value);
});

const renderedThought = computed(() => {
  if (!assistantThought.value) return '';
  return markdown.render(assistantThought.value);
});

const thoughtExpanded = ref(false);
const progressExpanded = ref(true);

const originalQueryVariant = computed(
  () => progressQueryVariants.value[0]?.trim() || ''
);
const expandedQueryVariants = computed(() =>
  progressQueryVariants.value
    .slice(1)
    .map((item) => item.trim())
    .filter(Boolean)
);
const progressExpansionStepIndex = computed(() =>
  progressSteps.value.findIndex((step) => /扩展|扩写/.test(step))
);

const formattedTime = computed(() => {
  const ts = props.message.timestamp;
  if (!ts) return '';
  return ts.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
});

function applyClarification(option: ClarificationOption) {
  emit('applyClarification', option);
}

function selectSource(source: SourceSummary) {
  emit('selectSource', source);
}

function buildSourceMeta(source: SourceSummary) {
  const parts = [source.source_label, source.knowledge_space, source.tags]
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  return parts.join(' · ');
}

function buildSourceSummary(source: SourceSummary) {
  return String(source.summary || '').trim();
}

function toggleThought() {
  thoughtExpanded.value = !thoughtExpanded.value;
}

function toggleProgress() {
  progressExpanded.value = !progressExpanded.value;
}
</script>

<template>
  <div
    :class="[
      'mb-6 flex w-full animate-o-fade-in',
      isUser ? 'justify-end' : 'justify-start'
    ]">
    <div
      :class="
        cn(
          'flex',
          'flex-col',
          'gap-3',
          isUser
            ? 'w-fit max-w-[min(78%,640px)] rounded-[24px_24px_8px_24px] bg-zinc-900 px-4 py-3.5 text-white shadow-[0_12px_32px_rgba(24,24,27,0.12)] max-sm:max-w-[88%]'
            : 'w-full max-w-[min(100%,760px)]',
          !isUser && isError && 'text-red-950',
          !isUser && isNoResult && 'text-amber-900'
        )
      ">
      <div
        v-if="!isUser"
        class="mb-3 ml-2 flex items-center justify-between gap-3 max-sm:ml-0 max-sm:flex-col max-sm:items-start">
        <div
          class="inline-flex items-center gap-2.5 text-[13px] font-semibold tracking-[0.01em] text-zinc-800">
          <div
            class="flex h-7 w-7 items-center justify-center rounded-full border border-black/5 bg-white shadow-sm">
            <RobotOutlined v-if="!isLoading" class="text-zinc-700" />
            <LoadingOutlined v-else class="animate-spin text-zinc-700" />
          </div>
          <span>RAG.Agent</span>
        </div>
        <span v-if="formattedTime" class="text-[11px] text-zinc-400">
          {{ formattedTime }}
        </span>
      </div>

      <section
        v-if="!isUser && hasProgressSection"
        class="mt-2 ml-2 max-sm:ml-0">
        <div
          class="rounded-2xl border border-black/5 bg-white/60 px-5 py-4 shadow-sm transition-all duration-200 hover:bg-white/85 hover:shadow-md">
          <button
            type="button"
            class="flex w-full justify-between items-center gap-3 text-left"
            @click="toggleProgress">
            <div
              class="flex items-center text-xs font-bold uppercase tracking-wide text-zinc-500">
              执行进度
              <LoadingOutlined
                v-if="isLoading && !hasAnswerSection"
                class="text-xs text-zinc-400" />
            </div>

            <span
              class="flex items-center ml-auto text-xs font-semibold text-zinc-500">
              {{ progressExpanded ? '收起' : '展开' }}
              <DownOutlined
                :class="[
                  'text-xs transition-transform duration-200',
                  progressExpanded ? 'rotate-180' : ''
                ]" />
            </span>
          </button>
          <div v-if="progressExpanded" class="mt-4 flex flex-col gap-0">
            <div
              v-for="(step, index) in progressSteps"
              :key="`${message.id}-progress-${index}`"
              :class="[
                'grid grid-cols-[20px_minmax(0,1fr)] items-start gap-2 text-[13px] transition-colors',
                index === progressSteps.length - 1
                  ? 'font-medium text-zinc-800'
                  : 'text-zinc-500'
              ]">
              <div class="flex h-full flex-col items-center pt-[0.4rem]">
                <span
                  :class="[
                    'h-2 w-2 shrink-0 rounded-full transition-all',
                    index === progressSteps.length - 1
                      ? 'bg-zinc-700 shadow-[0_0_0_3px_rgba(24,24,27,0.1)]'
                      : 'bg-zinc-300'
                  ]" />
                <div
                  v-if="index !== progressSteps.length - 1"
                  class="my-1.5 min-h-3.5 w-[1.5px] flex-1 rounded-full bg-zinc-200"></div>
              </div>
              <div class="pb-2.5">
                <span class="block leading-relaxed">{{ step }}</span>
                <div
                  v-if="
                    index === progressExpansionStepIndex &&
                    expandedQueryVariants.length > 0
                  "
                  class="mt-3 rounded-2xl border border-black/6 bg-zinc-50 px-4 py-3.5">
                  <div class="text-[12px] font-semibold text-zinc-700">
                    问题扩写
                  </div>
                  <div
                    v-if="originalQueryVariant"
                    class="mt-2 text-[12px] leading-6 text-zinc-500">
                    原始问法：{{ originalQueryVariant }}
                  </div>
                  <ul class="mt-2 space-y-2 text-[13px] text-zinc-700">
                    <li
                      v-for="(variant, variantIndex) in expandedQueryVariants"
                      :key="`${message.id}-variant-${variantIndex}`"
                      class="flex gap-2 items-center">
                      <span
                        class="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400"></span>
                      <span class="leading-6">{{ variant }}</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        v-if="!isUser && hasThoughtSection"
        class="mt-3 ml-2 max-sm:ml-0">
        <button
          type="button"
          class="flex w-full items-center gap-3 rounded-2xl bg-zinc-100 px-4 py-3 text-zinc-700 transition-all duration-200 hover:bg-zinc-200 hover:shadow-sm"
          @click="toggleThought">
          <span class="text-sm font-semibold">思考过程</span>
          <span class="ml-auto text-xs font-semibold text-zinc-500">
            {{ thoughtExpanded ? '收起' : '展开' }}
          </span>
          <DownOutlined
            :class="[
              'text-xs transition-transform duration-200',
              thoughtExpanded ? 'rotate-180' : ''
            ]" />
        </button>
        <div
          v-if="thoughtExpanded"
          class="o-markdown mt-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-5 py-4 text-zinc-500 shadow-inner"
          v-html="renderedThought" />
      </section>

      <template v-if="isLoading && !message.content">
        <div class="mt-3 ml-2 flex flex-col gap-3 max-sm:ml-0">
          <div
            class="h-3.5 w-[92%] animate-pulse rounded-full bg-linear-to-r from-zinc-100 via-zinc-200 to-zinc-100" />
          <div
            class="h-3.5 w-[84%] animate-pulse rounded-full bg-linear-to-r from-zinc-100 via-zinc-200 to-zinc-100" />
          <div
            class="h-3.5 w-[60%] animate-pulse rounded-full bg-linear-to-r from-zinc-100 via-zinc-200 to-zinc-100" />
        </div>
      </template>

      <template v-else-if="isNoResult">
        <div
          class="mt-3 ml-2 flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 px-5 py-4 shadow-sm max-sm:ml-0">
          <WarningOutlined class="mt-1 text-base text-amber-600" />
          <div class="flex-1">
            <div
              v-if="hasKnowledgeSpaceLabel"
              class="mb-3 inline-flex items-center rounded-full border border-amber-300/70 bg-white/70 px-3 py-1 text-[11px] font-semibold tracking-[0.02em] text-amber-800">
              所属知识空间：{{ knowledgeSpaceLabel }}
            </div>
            <div class="o-markdown text-amber-800" v-html="renderedAnswer" />
          </div>
        </div>
      </template>

      <template v-else>
        <section
          v-if="!isUser && hasAnswerSection"
          :class="
            cn(
              'mt-3 ml-2 rounded-2xl border border-black/6 bg-white px-6 py-5 shadow-[0_8px_24px_rgba(24,24,27,0.06)] max-sm:ml-0 max-sm:px-5',
              isError && 'border-red-200 bg-red-50'
            )
          ">
          <div class="flex justify-between items-center w-full">
            <div
              class="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-400">
              回答
            </div>
            <div
              v-if="hasKnowledgeSpaceLabel"
              class="mb-4 inline-flex items-center rounded-full border border-black/8 bg-zinc-50 px-3 py-1 text-[11px] font-semibold tracking-[0.02em] text-zinc-700">
              所属知识空间：{{ knowledgeSpaceLabel }}
            </div>
          </div>

          <div class="o-markdown answer-body" v-html="renderedAnswer" />
          <div
            v-if="hasSources"
            class="mt-3 flex flex-wrap items-start gap-2.5 border-t border-black/6 pt-4">
            <div
              class="pt-1.5 text-xs font-bold uppercase tracking-wide text-zinc-500">
              引用来源
            </div>
            <div class="flex flex-1 flex-wrap gap-2">
              <button
                v-for="source in sourceItems"
                :key="`${message.id}-${source.doc_id}-${source.chunk_index}`"
                type="button"
                class="flex w-48 max-w-full items-start gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-xs text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-100 hover:shadow-sm"
                @click="selectSource(source)">
                <span
                  class="flex h-5 min-w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold text-zinc-950 shadow-sm ring-1 ring-black/5">
                  {{ source.index }}
                </span>
                <span class="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                  <span class="block max-w-35 truncate">
                    {{ source.filename }}
                  </span>
                  <span
                    v-if="buildSourceSummary(source)"
                    class="o-source-summary text-left text-[11px] text-zinc-500">
                    {{ buildSourceSummary(source) }}
                  </span>
                  <span
                    v-else-if="buildSourceMeta(source)"
                    class="whitespace-nowrap text-[11px] text-zinc-500">
                    {{ buildSourceMeta(source) }}
                  </span>
                </span>
              </button>
            </div>
          </div>
          <div v-if="hasClarification" class="mt-3 flex flex-wrap gap-3">
            <button
              v-for="option in clarificationOptions"
              :key="`${message.id}-${option.field}-${option.value}`"
              type="button"
              class="rounded-full border border-black/8 bg-white px-4 py-2.5 text-sm font-semibold text-zinc-900 shadow-sm transition-all duration-200 hover:border-success-border hover:bg-[rgba(238,247,241,0.92)] hover:text-(--color-success-strong) hover:shadow"
              @click="applyClarification(option)">
              {{ option.label }}
            </button>
          </div>
        </section>

        <div
          v-else-if="!isUser"
          :class="
            cn(
              'o-markdown ml-2 max-sm:ml-0',
              isError &&
                'rounded-2xl border border-red-200 bg-red-50 px-6 py-5 shadow-sm'
            )
          "
          v-html="renderedContent" />

        <div
          v-if="!isUser && !hasAnswerSection && hasSources"
          class="ml-2 mt-3 flex flex-wrap items-start gap-2.5 border-t border-black/6 pt-4 max-sm:ml-0">
          <div
            class="pt-1.5 text-xs font-bold uppercase tracking-wide text-zinc-500">
            引用来源
          </div>
          <div class="flex flex-1 flex-wrap gap-2">
            <button
              v-for="source in sourceItems"
              :key="`${message.id}-fallback-${source.doc_id}-${source.chunk_index}`"
              type="button"
              class="flex w-48 max-w-full items-start gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-xs text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-100 hover:shadow-sm"
              @click="selectSource(source)">
              <span
                class="flex h-5 min-w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold text-zinc-950 shadow-sm ring-1 ring-black/5">
                {{ source.index }}
              </span>
              <span class="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                <span class="block max-w-35 truncate">
                  {{ source.filename }}
                </span>
                <span
                  v-if="buildSourceSummary(source)"
                  class="o-source-summary text-left text-[11px] text-zinc-500">
                  {{ buildSourceSummary(source) }}
                </span>
                <span
                  v-else-if="buildSourceMeta(source)"
                  class="whitespace-nowrap text-[11px] text-zinc-500">
                  {{ buildSourceMeta(source) }}
                </span>
              </span>
            </button>
          </div>
        </div>

        <div
          v-else-if="isUser"
          class="whitespace-pre-wrap text-sm leading-relaxed">
          {{ message.content }}
        </div>
      </template>
    </div>
  </div>
</template>
