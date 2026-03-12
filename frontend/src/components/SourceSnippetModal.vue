<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  CloseOutlined,
  LeftOutlined,
  RightOutlined
} from '@ant-design/icons-vue';
import { getApiBase } from '@/services/runtime';

interface SourceSummary {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  knowledge_space: string;
  category: string;
  topic: string;
  tags: string;
  version_label: string;
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

const API_BASE = getApiBase();

const excerpt = ref('');
const loading = ref(false);
const error = ref('');
const images = ref<SourceImage[]>([]);
const previewVisible = ref(false);
const activeImageIndex = ref(0);

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
    { label: '知识空间', value: props.source.knowledge_space },
    { label: '分类', value: props.source.category },
    { label: '主题', value: props.source.topic },
    { label: '标签', value: props.source.tags },
    { label: '版本/时效', value: props.source.version_label }
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
        `${API_BASE}/api/chat/sources/${encodeURIComponent(docId)}/${chunkIndex}`
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
          <div v-if="sourceMetaLines.length > 0" class="source-modal-tags">
            <span
              v-for="item in sourceMetaLines"
              :key="item.label"
              class="source-tag">
              {{ item.label }}：{{ item.value }}
            </span>
          </div>
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
      <div v-else class="source-modal-body">
        <div v-html="highlightedExcerpt" />
        <section v-if="images.length > 0" class="source-images">
          <div class="source-images-title">文档附图</div>
          <div class="source-image-groups">
            <section
              v-for="group in groupedImages"
              :key="group.title"
              class="source-image-group">
              <div class="source-image-group-title">{{ group.title }}</div>
              <div class="source-images-grid">
                <button
                  v-for="image in group.items"
                  :key="image.image_id"
                  class="source-image-card"
                  type="button"
                  @click="openImagePreview(image.image_id)">
                  <img
                    :src="image.url"
                    :alt="image.filename || image.source_label"
                    class="source-image-preview" />
                  <span class="source-image-label">
                    {{ image.source_label }}
                  </span>
                </button>
              </div>
            </section>
          </div>
        </section>
      </div>
    </div>

    <div
      v-if="previewVisible && activePreviewImage"
      class="gallery-backdrop"
      @click.self="closeImagePreview">
      <div class="gallery-shell">
        <button type="button" class="gallery-close" @click="closeImagePreview">
          <CloseOutlined />
        </button>

        <button
          v-if="flattenedImages.length > 1"
          type="button"
          class="gallery-nav gallery-nav-prev"
          @click="showPreviousImage">
          <LeftOutlined />
        </button>

        <figure class="gallery-figure">
          <img
            :src="activePreviewImage.url"
            :alt="
              activePreviewImage.filename || activePreviewImage.source_label
            "
            class="gallery-image" />
          <figcaption class="gallery-caption">
            <span class="gallery-caption-title">
              {{ activePreviewImage.source_label }}
            </span>
            <span class="gallery-caption-meta">
              {{ activeImageIndex + 1 }} / {{ flattenedImages.length }}
            </span>
          </figcaption>
        </figure>

        <button
          v-if="flattenedImages.length > 1"
          type="button"
          class="gallery-nav gallery-nav-next"
          @click="showNextImage">
          <RightOutlined />
        </button>
      </div>
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

.source-modal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.source-tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f5f8ff;
  border: 1px solid rgba(37, 99, 235, 0.12);
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
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

.source-images {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #f4f4f5;
}

.source-image-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.source-image-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-image-group-title {
  color: #52525b;
  font-size: 12px;
  font-weight: 700;
}

.source-images-title {
  color: #18181b;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}

.source-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.source-image-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e4e4e7;
  background: #fafafa;
  cursor: zoom-in;
  text-align: left;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.source-image-card:hover {
  transform: translateY(-2px);
  border-color: rgba(37, 99, 235, 0.24);
  box-shadow: 0 12px 28px rgba(24, 24, 27, 0.08);
}

.source-image-preview {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 12px;
  background: #f4f4f5;
}

.source-image-label {
  color: #3f3f46;
  font-size: 12px;
  font-weight: 600;
}

.gallery-backdrop {
  position: fixed;
  inset: 0;
  z-index: 140;
  background: rgba(9, 9, 11, 0.9);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.gallery-shell {
  position: relative;
  width: min(1120px, 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.gallery-close,
.gallery-nav {
  border: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.12);
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}

.gallery-close:hover,
.gallery-nav:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.04);
}

.gallery-close {
  position: absolute;
  top: -18px;
  right: 0;
  width: 42px;
  height: 42px;
  border-radius: 50%;
}

.gallery-nav {
  position: absolute;
  top: 50%;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  transform: translateY(-50%);
}

.gallery-nav:hover {
  transform: translateY(-50%) scale(1.04);
}

.gallery-nav-prev {
  left: 12px;
}

.gallery-nav-next {
  right: 12px;
}

.gallery-figure {
  width: min(920px, 100%);
  margin: 0;
}

.gallery-image {
  display: block;
  width: 100%;
  max-height: min(72vh, 900px);
  object-fit: contain;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.04);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
}

.gallery-caption {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: rgba(255, 255, 255, 0.88);
  font-size: 13px;
}

.gallery-caption-title {
  font-weight: 600;
}

.gallery-caption-meta {
  color: rgba(255, 255, 255, 0.62);
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

  .gallery-backdrop {
    padding: 16px;
  }

  .gallery-close {
    top: -8px;
    right: 4px;
  }

  .gallery-nav {
    width: 40px;
    height: 40px;
  }

  .gallery-nav-prev {
    left: 0;
  }

  .gallery-nav-next {
    right: 0;
  }

  .gallery-caption {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
