<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { CloseOutlined } from '@ant-design/icons-vue';

interface SourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  summary: string;
}

const props = defineProps<{
  visible: boolean;
  source: SourceSummary | null;
  queryText?: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const excerpt = ref('');
const loading = ref(false);
const error = ref('');

const sourceKeywords = computed(() => extractKeywords(props.queryText || ''));

const highlightedExcerpt = computed(() => {
  if (!excerpt.value) return '';
  return highlightKeywords(excerpt.value, sourceKeywords.value);
});

watch(
  () => [props.visible, props.source?.doc_id, props.source?.chunk_index],
  async ([visible, docId, chunkIndex]) => {
    if (!visible || !docId || typeof chunkIndex !== 'number') {
      excerpt.value = '';
      loading.value = false;
      error.value = '';
      return;
    }

    excerpt.value = '';
    error.value = '';
    loading.value = true;

    try {
      const response = await fetch(
        `${API_BASE}/api/chat/sources/${encodeURIComponent(docId)}/${chunkIndex}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      excerpt.value = typeof data.excerpt === 'string' ? data.excerpt : '';
    } catch (fetchError: unknown) {
      error.value =
        fetchError instanceof Error ? fetchError.message : '片段加载失败';
    } finally {
      loading.value = false;
    }
  },
  { immediate: true }
);

function closeModal() {
  emit('close');
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function extractKeywords(query: string) {
  const matches = query.match(/[\u4e00-\u9fff]{2,}|[A-Za-z0-9_-]{2,}/g) || [];
  const terms: string[] = [];

  for (const match of matches) {
    const token = match.trim();
    if (!token) continue;

    terms.push(token);

    if (/^[\u4e00-\u9fff]+$/.test(token)) {
      for (let size = 2; size <= Math.min(token.length, 4); size += 1) {
        for (let start = 0; start <= token.length - size; start += 1) {
          terms.push(token.slice(start, start + size));
        }
      }
    }
  }

  return [...new Set(terms.filter(Boolean))].sort(
    (left, right) => right.length - left.length
  );
}

function highlightKeywords(text: string, keywords: string[]) {
  let html = escapeHtml(text);

  for (const keyword of keywords) {
    const pattern = new RegExp(`(${escapeRegExp(escapeHtml(keyword))})`, 'gi');
    html = html.replace(pattern, '<mark class="keyword-hit">$1</mark>');
  }

  return html.replace(/\n/g, '<br>');
}
</script>

<template>
  <div
    v-if="visible && source"
    class="source-modal-backdrop"
    @click.self="closeModal">
    <div class="source-modal">
      <div class="source-modal-head">
        <div>
          <div class="source-modal-title">{{ source.filename }}</div>
          <div class="source-modal-meta">片段 {{ source.chunk_index + 1 }}</div>
        </div>
        <button type="button" class="source-modal-close" @click="closeModal">
          <CloseOutlined />
        </button>
      </div>
      <div class="source-modal-tip">已按当前问题中的命中关键词进行高亮。</div>
      <div v-if="loading" class="source-modal-body source-modal-state">
        正在加载原文片段...
      </div>
      <div
        v-else-if="error"
        class="source-modal-body source-modal-state source-modal-error">
        片段加载失败：{{ error }}
      </div>
      <div v-else class="source-modal-body" v-html="highlightedExcerpt" />
    </div>
  </div>
</template>

<style scoped>
.source-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(24, 24, 27, 0.42);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 120;
}

.source-modal {
  width: min(760px, 100%);
  max-height: min(80vh, 860px);
  overflow: hidden;
  background: #ffffff;
  border-radius: 24px;
  box-shadow: 0 24px 60px rgba(24, 24, 27, 0.22);
  border: 1px solid rgba(24, 24, 27, 0.08);
}

.source-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 22px 14px;
  border-bottom: 1px solid #f4f4f5;
}

.source-modal-title {
  color: #18181b;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.source-modal-meta,
.source-modal-tip {
  color: #71717a;
  font-size: 13px;
}

.source-modal-tip {
  padding: 14px 22px 0;
}

.source-modal-close {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  background: #f4f4f5;
  color: #18181b;
  cursor: pointer;
}

.source-modal-body {
  padding: 18px 22px 24px;
  max-height: calc(80vh - 110px);
  overflow-y: auto;
  color: #27272a;
  line-height: 1.85;
  font-size: 14px;
  white-space: normal;
}

.source-modal-state {
  color: #71717a;
}

.source-modal-error {
  color: #dc2626;
}

.source-modal-body :deep(.keyword-hit) {
  background: #fef08a;
  color: #854d0e;
  padding: 0 2px;
  border-radius: 4px;
}

@media (max-width: 640px) {
  .source-modal-backdrop {
    padding: 14px;
  }

  .source-modal-head,
  .source-modal-tip,
  .source-modal-body {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
