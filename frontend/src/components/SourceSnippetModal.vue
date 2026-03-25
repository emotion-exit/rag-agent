<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { LeftOutlined, RightOutlined } from '@ant-design/icons-vue';
import { getApiBase } from '@/services/runtime';
import { buildPublicConfigHeaders } from '@/services/publicConfig';
import { OModal } from '@/orange-ui';

interface SourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  knowledge_space: string;
  tags: string;
  source_type: string;
  source_label: string;
  source_page: number;
  section_title?: string;
  heading_path?: string;
  image_count?: number;
  summary: string;
}

interface SourceImage {
  image_id: string;
  filename: string;
  source_label: string;
  source_page: number;
  url: string;
}

const props = defineProps<{
  visible: boolean;
  source: SourceSummary | null;
  queryText?: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const excerpt = ref('');
const loading = ref(false);
const error = ref('');
const images = ref<SourceImage[]>([]);
const previewVisible = ref(false);
const activeImageIndex = ref(0);

function buildApiUrl(path: string) {
  return `${getApiBase()}${path}`;
}

const flattenedImages = computed(() =>
  [...images.value].sort((left, right) => {
    const pageDiff = left.source_page - right.source_page;
    if (pageDiff !== 0) return pageDiff;
    return left.source_label.localeCompare(right.source_label, 'zh-CN');
  })
);

const activePreviewImage = computed(
  () => flattenedImages.value[activeImageIndex.value] ?? null
);

const groupedImages = computed(() => {
  const groups = new Map<string, { title: string; items: SourceImage[] }>();

  for (const image of flattenedImages.value) {
    const key = image.source_page > 0 ? `page-${image.source_page}` : 'ordered';
    const title =
      image.source_page > 0 ? `第 ${image.source_page} 页` : '按文档顺序';

    if (!groups.has(key)) {
      groups.set(key, { title, items: [] });
    }

    groups.get(key)?.items.push(image);
  }

  return Array.from(groups.values());
});

const sourceKeywords = computed(() => extractKeywords(props.queryText || ''));
const sourceMetaLines = computed(() => {
  if (!props.source) return [];

  return [
    {
      label: '来源类型',
      value: '正文文本'
    },
    { label: '来源位置', value: props.source.source_label },
    {
      label: '文档附图',
      value: images.value.length > 0 ? `共 ${images.value.length} 张` : ''
    },
    { label: '章节路径', value: props.source.heading_path || '' },
    { label: '章节标题', value: props.source.section_title || '' },
    { label: '知识库', value: props.source.knowledge_space },
    { label: '标签', value: props.source.tags }
  ].filter((item) => item.value?.trim());
});

const highlightedExcerpt = computed(() => {
  if (!excerpt.value) return '';
  return highlightKeywords(excerpt.value, sourceKeywords.value);
});

watch(
  () => [props.visible, props.source?.doc_id, props.source?.chunk_index],
  async ([visible, docId, chunkIndex]) => {
    if (!visible || !docId || typeof chunkIndex !== 'number') {
      excerpt.value = '';
      images.value = [];
      loading.value = false;
      error.value = '';
      previewVisible.value = false;
      return;
    }

    excerpt.value = '';
    images.value = [];
    error.value = '';
    loading.value = true;

    try {
      const response = await fetch(
        buildApiUrl(
          `/api/chat/sources/${encodeURIComponent(docId)}/${chunkIndex}`
        ),
        {
          headers: buildPublicConfigHeaders()
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      excerpt.value = typeof data.excerpt === 'string' ? data.excerpt : '';
      images.value = Array.isArray(data.images) ? data.images : [];
    } catch (fetchError: unknown) {
      error.value =
        fetchError instanceof Error ? fetchError.message : '片段加载失败';
    } finally {
      loading.value = false;
    }
  },
  { immediate: true }
);

watch(flattenedImages, (nextImages) => {
  if (nextImages.length === 0) {
    previewVisible.value = false;
    activeImageIndex.value = 0;
    return;
  }

  if (activeImageIndex.value >= nextImages.length) {
    activeImageIndex.value = nextImages.length - 1;
  }
});

function closeModal() {
  emit('close');
}

function openImagePreview(imageId: string) {
  const nextIndex = flattenedImages.value.findIndex(
    (image) => image.image_id === imageId
  );

  if (nextIndex < 0) return;

  activeImageIndex.value = nextIndex;
  previewVisible.value = true;
}

function closeImagePreview() {
  previewVisible.value = false;
}

function showPreviousImage() {
  if (flattenedImages.value.length <= 1) return;

  activeImageIndex.value =
    (activeImageIndex.value - 1 + flattenedImages.value.length) %
    flattenedImages.value.length;
}

function showNextImage() {
  if (flattenedImages.value.length <= 1) return;

  activeImageIndex.value =
    (activeImageIndex.value + 1) % flattenedImages.value.length;
}

function handleKeydown(event: KeyboardEvent) {
  if (!props.visible) return;

  if (previewVisible.value) {
    if (event.key === 'Escape') {
      closeImagePreview();
      return;
    }

    if (event.key === 'ArrowLeft') {
      showPreviousImage();
      return;
    }

    if (event.key === 'ArrowRight') {
      showNextImage();
    }

    return;
  }

  if (event.key === 'Escape') {
    closeModal();
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown);
});

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

const QUERY_STOPWORDS = new Set([
  '请问',
  '一下',
  '一下子',
  '这个',
  '那个',
  '怎么',
  '如何',
  '多少',
  '什么',
  '哪些',
  '是否',
  '可以',
  '需要',
  '帮我',
  '告诉我',
  '有没有',
  '吗',
  '呢',
  '呀',
  '啊',
  '吧',
  '的',
  '了',
  '和',
  '与',
  '及',
  '或',
  '并',
  '在',
  '是'
]);

function normalizeQueryText(value: string) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, '');
}

function splitChineseToken(token: string) {
  let parts = [token];

  for (const stopword of QUERY_STOPWORDS) {
    if (!/[\u4e00-\u9fff]/.test(stopword)) continue;

    parts = parts.flatMap((part) =>
      part.split(stopword).map((item) => item.trim())
    );
  }

  return parts.filter((part) => part.length >= 2);
}

function extractKeywords(query: string) {
  const normalizedQuery = normalizeQueryText(query);
  const matches =
    normalizedQuery.match(/[\u4e00-\u9fff]{2,}|[a-z0-9_-]{2,}/g) || [];
  const terms: string[] = [];

  for (const match of matches) {
    const token = match.trim();
    if (!token || QUERY_STOPWORDS.has(token)) continue;

    terms.push(token);

    if (/^[\u4e00-\u9fff]+$/.test(token)) {
      const splitTerms = splitChineseToken(token);
      terms.push(...splitTerms);

      for (const splitTerm of splitTerms) {
        if (splitTerm.length < 3) continue;

        for (let size = Math.min(splitTerm.length, 4); size >= 2; size -= 1) {
          for (let start = 0; start <= splitTerm.length - size; start += 1) {
            const piece = splitTerm.slice(start, start + size);
            if (!QUERY_STOPWORDS.has(piece)) {
              terms.push(piece);
            }
          }
        }
      }
    }
  }

  return [...new Set(terms.filter(Boolean))].sort(
    (left, right) => right.length - left.length
  );
}

function buildHighlightRanges(text: string, keywords: string[]) {
  const ranges: Array<{ start: number; end: number }> = [];

  for (const keyword of keywords) {
    const trimmedKeyword = keyword.trim();
    if (trimmedKeyword.length < 2) continue;

    const pattern = new RegExp(escapeRegExp(trimmedKeyword), 'gi');
    let match: RegExpExecArray | null = null;

    while ((match = pattern.exec(text)) !== null) {
      const start = match.index;
      const end = start + match[0].length;
      if (start === end) break;

      ranges.push({ start, end });

      if (pattern.lastIndex === start) {
        pattern.lastIndex += 1;
      }
    }
  }

  ranges.sort((left, right) => {
    if (left.start !== right.start) return left.start - right.start;
    return right.end - left.end;
  });

  const merged: Array<{ start: number; end: number }> = [];
  for (const range of ranges) {
    const previous = merged[merged.length - 1];
    if (!previous) {
      merged.push(range);
      continue;
    }

    if (range.start < previous.end) {
      continue;
    }

    merged.push(range);
  }

  return merged;
}

function highlightKeywords(text: string, keywords: string[]) {
  if (!text) return '';

  const matchedKeywords = keywords.filter((keyword, index) => {
    const trimmedKeyword = keyword.trim();
    if (trimmedKeyword.length < 2) return false;

    const normalizedText = text.toLowerCase();
    if (!normalizedText.includes(trimmedKeyword.toLowerCase())) {
      return false;
    }

    return !keywords
      .slice(0, index)
      .some((existing) => existing.includes(trimmedKeyword));
  });

  const ranges = buildHighlightRanges(text, matchedKeywords);
  if (ranges.length === 0) {
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  let cursor = 0;
  let html = '';

  for (const range of ranges) {
    if (cursor < range.start) {
      html += escapeHtml(text.slice(cursor, range.start));
    }

    html += `<mark class="o-keyword-hit">${escapeHtml(
      text.slice(range.start, range.end)
    )}</mark>`;
    cursor = range.end;
  }

  if (cursor < text.length) {
    html += escapeHtml(text.slice(cursor));
  }

  return html.replace(/\n/g, '<br>');
}
</script>

<template>
  <OModal
    v-if="source"
    :visible="visible"
    :title="source.filename"
    :subtitle="`片段 ${source.chunk_index + 1}`"
    width="min(760px, 100%)"
    class="border border-black/5 bg-white/95 p-0 shadow-[0_24px_60px_rgba(24,24,27,0.22)]"
    @close="closeModal">
    <template #header>
      <div class="flex min-w-0 flex-1 flex-col gap-2 pr-4">
        <div class="truncate text-[18px] font-bold leading-7 text-zinc-900">
          {{ source.filename }}
        </div>
        <div class="text-[13px] text-zinc-500">
          片段 {{ source.chunk_index + 1 }}
        </div>
        <div v-if="sourceMetaLines.length > 0" class="flex flex-wrap gap-2">
          <span
            v-for="item in sourceMetaLines"
            :key="item.label"
            class="inline-flex min-h-7 items-center rounded-full border border-success-border bg-success-soft px-2.5 py-1 text-xs font-semibold text-(--color-success-strong)">
            {{ item.label }}：{{ item.value }}
          </span>
        </div>
      </div>
    </template>

    <div class="overflow-hidden">
      <div
        class="border-t border-zinc-100 px-6 pt-4 text-[13px] text-zinc-500 sm:px-8">
        已按当前问题中的命中关键词进行高亮。
      </div>

      <div
        v-if="loading"
        class="max-h-[calc(80vh-110px)] overflow-y-auto px-6 pb-6 pt-4 text-sm leading-7 text-zinc-500 sm:px-8">
        正在加载原文片段...
      </div>
      <div
        v-else-if="error"
        class="max-h-[calc(80vh-110px)] overflow-y-auto px-6 pb-6 pt-4 text-sm leading-7 text-red-600 sm:px-8">
        片段加载失败：{{ error }}
      </div>
      <div
        v-else
        class="max-h-[calc(80vh-110px)] overflow-y-auto px-6 pb-6 pt-4 text-sm leading-[1.85] text-zinc-800 sm:px-8">
        <div class="source-excerpt" v-html="highlightedExcerpt" />
        <section
          v-if="images.length > 0"
          class="mt-5 border-t border-zinc-100 pt-4.5">
          <div class="mb-3 text-sm font-bold text-zinc-900">文档附图</div>
          <div class="flex flex-col gap-4.5">
            <section
              v-for="group in groupedImages"
              :key="group.title"
              class="flex flex-col gap-2.5">
              <div class="text-xs font-bold text-zinc-600">
                {{ group.title }}
              </div>
              <div
                class="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
                <button
                  v-for="image in group.items"
                  :key="image.image_id"
                  type="button"
                  class="flex w-full flex-col gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 p-2.5 text-left transition duration-200 hover:-translate-y-0.5 hover:border-success-border hover:shadow-[0_12px_28px_rgba(24,24,27,0.08)]"
                  @click="openImagePreview(image.image_id)">
                  <img
                    :src="image.url"
                    :alt="image.filename || image.source_label"
                    class="aspect-4/3 w-full rounded-xl bg-zinc-100 object-cover" />
                  <span class="text-xs font-semibold text-zinc-700">
                    {{ image.source_label }}
                  </span>
                </button>
              </div>
            </section>
          </div>
        </section>
      </div>
    </div>
  </OModal>

  <Teleport to="body">
    <div
      v-if="previewVisible && activePreviewImage"
      class="fixed inset-0 z-10020 flex items-center justify-center bg-black/90 p-4 backdrop-blur-[10px] sm:p-7"
      @click.self="closeImagePreview">
      <div class="relative flex w-full max-w-280 items-center justify-center">
        <button
          type="button"
          class="absolute right-1 top-0 inline-flex h-10 w-10 -translate-y-2 items-center justify-center rounded-full bg-white/15 text-white transition hover:scale-105 hover:bg-white/20 sm:right-0 sm:h-10.5 sm:w-10.5 sm:-translate-y-4"
          @click="closeImagePreview">
          ✕
        </button>

        <button
          v-if="flattenedImages.length > 1"
          type="button"
          class="absolute left-0 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white transition hover:scale-105 hover:bg-white/20 sm:left-3 sm:h-12 sm:w-12"
          @click="showPreviousImage">
          <LeftOutlined />
        </button>

        <figure class="m-0 w-full max-w-230">
          <img
            :src="activePreviewImage.url"
            :alt="
              activePreviewImage.filename || activePreviewImage.source_label
            "
            class="block max-h-[72vh] w-full rounded-[20px] bg-white/5 object-contain shadow-[0_24px_60px_rgba(0,0,0,0.35)]" />
          <figcaption
            class="mt-3.5 flex flex-col gap-2 text-[13px] text-white/90 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <span class="font-semibold">
              {{ activePreviewImage.source_label }}
            </span>
            <span class="text-white/60">
              {{ activeImageIndex + 1 }} / {{ flattenedImages.length }}
            </span>
          </figcaption>
        </figure>

        <button
          v-if="flattenedImages.length > 1"
          type="button"
          class="absolute right-0 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white transition hover:scale-105 hover:bg-white/20 sm:right-3 sm:h-12 sm:w-12"
          @click="showNextImage">
          <RightOutlined />
        </button>
      </div>
    </div>
  </Teleport>
</template>
