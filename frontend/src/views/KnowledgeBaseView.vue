<script setup lang="ts">
defineOptions({
  name: 'KnowledgeBaseView'
});

import { computed, onMounted, ref } from 'vue';
import {
  UploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';

interface DocumentInfo {
  doc_id: string;
  filename: string;
  upload_time: string;
  system_name: string;
  module_name: string;
  feature_name: string;
  version_name: string;
  doc_type: string;
  image_count: number;
}

interface Stats {
  total_chunks: number;
  total_documents: number;
}

interface UploadMetadataForm {
  system_name: string;
  module_name: string;
  feature_name: string;
  version_name: string;
  doc_type: string;
}

type ToastType = 'success' | 'error';
type KnowledgeBaseTab = 'upload' | 'documents';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const DOC_TYPE_OPTIONS = [
  '用户手册',
  '操作指南',
  '常见问题',
  '故障排查',
  '发布说明',
  '其他'
];

const documents = ref<DocumentInfo[]>([]);
const stats = ref<Stats>({ total_chunks: 0, total_documents: 0 });
const loading = ref(false);
const uploading = ref(false);
const isDragOver = ref(false);
const activeTab = ref<KnowledgeBaseTab>('upload');
const uploadForm = ref<UploadMetadataForm>({
  system_name: '',
  module_name: '',
  feature_name: '',
  version_name: '',
  doc_type: DOC_TYPE_OPTIONS[0] ?? '用户手册'
});
const toast = ref<{ visible: boolean; type: ToastType; message: string }>({
  visible: false,
  type: 'success',
  message: ''
});

const uploadMetadataPreview = computed(() => [
  { label: '所属系统', value: uploadForm.value.system_name || '未填写' },
  { label: '业务模块', value: uploadForm.value.module_name || '未填写' },
  { label: '功能主题', value: uploadForm.value.feature_name || '未填写' },
  { label: '适用版本', value: uploadForm.value.version_name || '未填写' },
  { label: '文档类型', value: uploadForm.value.doc_type || '未填写' }
]);

const knowledgeTabs = [
  {
    key: 'upload' as const,
    label: '上传文档',
    description: '录入新知识并附带分类元数据'
  },
  {
    key: 'documents' as const,
    label: '文档列表',
    description: '浏览、刷新和删除当前知识库资产'
  }
];

function showToast(message: string, type: ToastType = 'success') {
  toast.value = { visible: true, type, message };
  window.setTimeout(() => {
    toast.value.visible = false;
  }, 2800);
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return FilePdfOutlined;
  if (ext === 'doc' || ext === 'docx') return FileWordOutlined;
  return FileTextOutlined;
}

function formatDate(text: string) {
  if (!text) return '-';
  try {
    return new Date(text).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return text;
  }
}

function formatMetadata(value: string) {
  return value?.trim() || '未设置';
}

function formatImageCount(value: number) {
  return value > 0 ? `附图 ${value} 张` : '无附图';
}

async function fetchDocuments() {
  loading.value = true;
  try {
    const [docsRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/api/knowledge-base/documents`),
      fetch(`${API_BASE}/api/knowledge-base/stats`)
    ]);
    if (!docsRes.ok) throw new Error(`HTTP ${docsRes.status}`);
    if (!statsRes.ok) throw new Error(`HTTP ${statsRes.status}`);

    const docsData = await docsRes.json();
    const statsData = await statsRes.json();
    documents.value = docsData.documents || [];
    stats.value = statsData;
  } catch {
    showToast('加载文档列表失败，请检查后端服务是否正常运行', 'error');
  } finally {
    loading.value = false;
  }
}

async function processFiles(fileList: FileList | File[]) {
  if (fileList.length === 0) return;

  const maxSize = 20 * 1024 * 1024;
  uploading.value = true;

  try {
    for (const file of Array.from(fileList)) {
      if (file.size > maxSize) {
        showToast(`文件“${file.name}”过大，最大支持 20 MB`, 'error');
        continue;
      }

      const formData = new FormData();
      formData.append('file', file);
      formData.append('system_name', uploadForm.value.system_name.trim());
      formData.append('module_name', uploadForm.value.module_name.trim());
      formData.append('feature_name', uploadForm.value.feature_name.trim());
      formData.append('version_name', uploadForm.value.version_name.trim());
      formData.append('doc_type', uploadForm.value.doc_type.trim());

      const response = await fetch(`${API_BASE}/api/knowledge-base/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      showToast(data.message || '上传成功');
    }

    await fetchDocuments();
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`上传失败：${errMsg}`, 'error');
  } finally {
    uploading.value = false;
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;
  processFiles(input.files);
  input.value = '';
}

function handleDragOver(event: DragEvent) {
  event.preventDefault();
  isDragOver.value = true;
}

function handleDragLeave(event: DragEvent) {
  event.preventDefault();
  isDragOver.value = false;
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  isDragOver.value = false;
  if (event.dataTransfer?.files) {
    processFiles(event.dataTransfer.files);
  }
}

async function deleteDocument(doc: DocumentInfo) {
  if (!window.confirm(`确定删除“${doc.filename}”吗？`)) {
    return;
  }

  try {
    const response = await fetch(
      `${API_BASE}/api/knowledge-base/documents/${doc.doc_id}`,
      {
        method: 'DELETE'
      }
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    showToast(`已删除文档“${doc.filename}”`);
    await fetchDocuments();
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除失败：${errMsg}`, 'error');
  }
}

onMounted(() => {
  fetchDocuments();
});
</script>

<template>
  <div class="kb-container">
    <section class="panel-block panel-tabs-block">
      <div class="tab-strip" role="tablist" aria-label="知识库功能切换">
        <button
          v-for="tab in knowledgeTabs"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :class="['tab-pill', activeTab === tab.key ? 'tab-pill-active' : '']"
          @click="activeTab = tab.key">
          <span class="tab-pill-title">{{ tab.label }}</span>
          <span class="tab-pill-desc">{{ tab.description }}</span>
        </button>
      </div>
    </section>

    <section v-show="activeTab === 'upload'" class="panel-block">
      <div class="panel-head">
        <div>
          <div class="panel-title">上传文档</div>
          <div class="panel-subtitle">
            支持 PDF、Word、TXT、Markdown、CSV，单文件 20MB 以内。
          </div>
        </div>
      </div>

      <div class="metadata-grid">
        <label class="field-block">
          <span class="field-label">所属系统</span>
          <input
            v-model="uploadForm.system_name"
            class="field-input"
            type="text"
            maxlength="40"
            placeholder="例如：CRM、ERP、客服中台"
            :disabled="uploading" />
        </label>

        <label class="field-block">
          <span class="field-label">业务模块</span>
          <input
            v-model="uploadForm.module_name"
            class="field-input"
            type="text"
            maxlength="40"
            placeholder="例如：权限管理、订单中心"
            :disabled="uploading" />
        </label>

        <label class="field-block">
          <span class="field-label">功能主题</span>
          <input
            v-model="uploadForm.feature_name"
            class="field-input"
            type="text"
            maxlength="60"
            placeholder="例如：新增角色、导入订单"
            :disabled="uploading" />
        </label>

        <label class="field-block">
          <span class="field-label">适用版本</span>
          <input
            v-model="uploadForm.version_name"
            class="field-input"
            type="text"
            maxlength="30"
            placeholder="例如：V3.2、2026 春季版"
            :disabled="uploading" />
        </label>

        <label class="field-block field-block-wide">
          <span class="field-label">文档类型</span>
          <select
            v-model="uploadForm.doc_type"
            class="field-input field-select"
            :disabled="uploading">
            <option
              v-for="option in DOC_TYPE_OPTIONS"
              :key="option"
              :value="option">
              {{ option }}
            </option>
          </select>
        </label>
      </div>

      <div class="metadata-preview">
        <div
          v-for="item in uploadMetadataPreview"
          :key="item.label"
          class="metadata-chip">
          <span class="metadata-chip-label">{{ item.label }}</span>
          <span
            :class="[
              'metadata-chip-value',
              item.value === '未填写' ? 'metadata-chip-value-missing' : ''
            ]">
            {{ item.value }}
          </span>
        </div>
      </div>

      <label
        class="upload-zone"
        :class="{ dragging: isDragOver, busy: uploading }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop">
        <input
          type="file"
          class="hidden-input"
          multiple
          accept=".pdf,.docx,.txt,.md,.rst,.csv"
          :disabled="uploading"
          @change="handleFileSelect" />
        <div v-if="!uploading" class="upload-inner">
          <UploadOutlined class="upload-icon" />
          <div class="upload-title">点击选择文件，或将文件拖放到这里</div>
          <div class="upload-hint">
            上传后会自动抽取正文文本；文档图片会保留在引用详情中展示，但不参与检索
          </div>
        </div>
        <div v-else class="upload-inner">
          <LoadingOutlined class="upload-icon spin" />
          <div class="upload-title">正在处理文档并建立索引...</div>
          <div class="upload-hint">请稍候，完成后列表会自动刷新</div>
        </div>
      </label>
    </section>

    <section v-show="activeTab === 'documents'" class="panel-block">
      <div class="panel-head">
        <div>
          <div class="panel-title">已收录文档</div>
          <div class="panel-subtitle">
            这里展示可被聊天问答检索到的文档资产与分类元数据。
          </div>
        </div>
        <button
          class="refresh-btn"
          type="button"
          :disabled="loading"
          @click="fetchDocuments">
          <ReloadOutlined :class="{ spin: loading }" />
          刷新
        </button>
      </div>

      <section class="stats-grid section-stats-grid">
        <article class="stat-card">
          <div class="stat-icon blue"><DatabaseOutlined /></div>
          <div>
            <div class="stat-value">{{ stats.total_documents }}</div>
            <div class="stat-label">文档总数</div>
          </div>
        </article>
        <article class="stat-card">
          <div class="stat-icon green"><FileTextOutlined /></div>
          <div>
            <div class="stat-value">{{ stats.total_chunks }}</div>
            <div class="stat-label">分块</div>
          </div>
        </article>
      </section>

      <div class="docs-grid">
        <div v-if="loading && documents.length === 0" class="empty-state">
          <LoadingOutlined class="spin empty-icon" />
          <p>正在加载文档列表...</p>
        </div>
        <div v-else-if="documents.length === 0" class="empty-state">
          <DatabaseOutlined class="empty-icon" />
          <p>暂无文档，请先上传文件收录知识。</p>
        </div>
        <TransitionGroup name="list">
          <article v-for="doc in documents" :key="doc.doc_id" class="doc-card">
            <div class="doc-card-header">
              <div class="doc-title-wrapper">
                <div class="doc-icon-box">
                  <component :is="getFileIcon(doc.filename)" class="doc-icon" />
                </div>
                <h3 class="doc-title" :title="doc.filename">
                  {{ doc.filename }}
                </h3>
              </div>
              <button
                class="icon-action-btn delete-btn"
                type="button"
                title="删除文档"
                @click="deleteDocument(doc)">
                <DeleteOutlined />
              </button>
            </div>

            <div class="doc-tags">
              <span class="doc-tag type-tag">
                {{ formatMetadata(doc.doc_type) }}
              </span>
              <span class="doc-tag" v-if="doc.system_name || doc.module_name">
                {{ formatMetadata(doc.system_name) }}
                <span
                  v-if="doc.system_name && doc.module_name"
                  class="tag-divider">
                  /
                </span>
                {{ formatMetadata(doc.module_name) }}
              </span>
              <span class="doc-tag version-tag" v-if="doc.version_name">
                <span class="tag-dot"></span>
                {{ doc.version_name }}
              </span>
            </div>

            <div class="doc-card-footer">
              <div class="doc-meta-item">
                <span class="meta-label">上传于</span>
                <span class="meta-value">
                  {{ formatDate(doc.upload_time) }}
                </span>
              </div>
              <div class="doc-meta-item">
                <span
                  :class="[
                    'image-badge',
                    doc.image_count > 0 ? 'has-images' : 'no-images'
                  ]">
                  {{ formatImageCount(doc.image_count) }}
                </span>
              </div>
            </div>
          </article>
        </TransitionGroup>
      </div>
    </section>

    <Transition name="toast">
      <div v-if="toast.visible" :class="['toast', `toast-${toast.type}`]">
        <CheckCircleOutlined v-if="toast.type === 'success'" />
        <WarningOutlined v-else />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.kb-container {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding: 30px 0 64px;
}

.hero-block,
.panel-block,
.stat-card {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(24, 24, 27, 0.06);
  box-shadow: 0 20px 50px rgba(24, 24, 27, 0.04);
}

.hero-block {
  border-radius: 28px;
  padding: 32px;
  margin-bottom: 22px;
}

.eyebrow {
  color: #71717a;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.hero-block h1 {
  margin: 0 0 12px;
  font-size: 34px;
  line-height: 1.1;
  letter-spacing: -0.04em;
  color: #18181b;
}

.hero-block p {
  margin: 0;
  max-width: 640px;
  color: #71717a;
  line-height: 1.75;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 22px;
}

.section-stats-grid {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 24px;
  padding: 22px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.blue {
  background: #eff6ff;
  color: #2563eb;
}

.stat-icon.green {
  background: #ecfdf5;
  color: #059669;
}

.stat-value {
  color: #18181b;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.04em;
}

.stat-label {
  margin-top: 6px;
  color: #71717a;
  font-size: 13px;
}

.panel-block {
  border-radius: 28px;
  padding: 28px;
  margin-bottom: 22px;
}

.panel-tabs-block {
  padding: 14px;
}

.tab-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.tab-pill {
  border: 1px solid rgba(24, 24, 27, 0.08);
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
  color: #52525b;
  border-radius: 22px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.tab-pill:hover {
  transform: translateY(-1px);
  border-color: rgba(24, 24, 27, 0.14);
}

.tab-pill-active {
  background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 18px 36px rgba(24, 24, 27, 0.16);
}

.tab-pill-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.tab-pill-desc {
  font-size: 12px;
  line-height: 1.5;
  color: inherit;
  opacity: 0.82;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-title {
  color: #18181b;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.panel-subtitle {
  margin-top: 6px;
  color: #71717a;
  font-size: 13px;
}

.metadata-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-block-wide {
  grid-column: span 2;
}

.field-label {
  color: #3f3f46;
  font-size: 13px;
  font-weight: 600;
}

.field-input {
  width: 100%;
  border: 1px solid rgba(24, 24, 27, 0.12);
  border-radius: 16px;
  background: #fcfcfd;
  color: #18181b;
  font: inherit;
  padding: 12px 14px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
  background: #ffffff;
}

.field-input:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.field-select {
  appearance: none;
}

.metadata-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.metadata-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #f5f8ff;
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.metadata-chip-label {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.metadata-chip-value {
  color: #1f2937;
  font-size: 12px;
  font-weight: 600;
}

.metadata-chip-value-missing {
  color: #dc2626;
}

.upload-zone {
  display: block;
  border: 1.5px dashed #d4d4d8;
  border-radius: 24px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f7f7f8 100%);
  padding: 36px 20px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-zone.dragging {
  border-color: #18181b;
  background: #f5f5f5;
}

.upload-zone.busy {
  cursor: progress;
}

.hidden-input {
  display: none;
}

.upload-inner {
  text-align: center;
}

.upload-icon {
  font-size: 40px;
  color: #18181b;
  margin-bottom: 16px;
}

.upload-title {
  color: #18181b;
  font-size: 16px;
  font-weight: 600;
}

.upload-hint {
  margin-top: 8px;
  color: #71717a;
  font-size: 13px;
}

.refresh-btn,
.delete-btn {
  border: 0;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #18181b;
  color: #ffffff;
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 13px;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.docs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  position: relative;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: rgba(250, 250, 250, 0.5);
  border: 1px dashed rgba(24, 24, 27, 0.1);
  border-radius: 20px;
  color: #71717a;
  text-align: center;
}

.empty-icon {
  font-size: 32px;
  color: #a1a1aa;
  margin-bottom: 12px;
}

.doc-card {
  background: #ffffff;
  border: 1px solid rgba(24, 24, 27, 0.08);
  border-radius: 20px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.doc-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(24, 24, 27, 0.06);
  border-color: rgba(37, 99, 235, 0.3);
}

.doc-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.doc-title-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.doc-icon-box {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #f4f4f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #52525b;
  font-size: 20px;
}

.doc-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #18181b;
  line-height: 1.4;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
  padding-top: 2px;
}

.icon-action-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #a1a1aa;
  transition: all 0.2s ease;
}

.icon-action-btn:hover.delete-btn {
  background: #fef2f2;
  color: #dc2626;
}

.doc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.doc-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #f4f4f5;
  color: #52525b;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}

.type-tag {
  background: #eff6ff;
  color: #2563eb;
}

.version-tag {
  background: #f0fdf4;
  color: #059669;
}

.tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  margin-right: 6px;
}

.tag-divider {
  margin: 0 4px;
  color: #a1a1aa;
}

.doc-card-footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid rgba(24, 24, 27, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.doc-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-label {
  font-size: 11px;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.meta-value {
  font-size: 13px;
  color: #52525b;
  font-weight: 500;
}

.image-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.image-badge.has-images {
  color: #1d4ed8;
  background: #eff6ff;
}

.image-badge.no-images {
  color: #a1a1aa;
  background: #f4f4f5;
}

/* 列表动画 */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(15px);
}
.list-leave-active {
  position: absolute;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 12px 16px;
  box-shadow: 0 20px 40px rgba(24, 24, 27, 0.16);
  z-index: 200;
}

.toast-success {
  background: #18181b;
  color: #ffffff;
}

.toast-error {
  background: #dc2626;
  color: #ffffff;
}

.spin {
  animation: spin 1s linear infinite;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.24s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 14px);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .kb-container {
    padding: 0 0 40px;
  }

  .hero-block,
  .panel-block {
    padding: 22px 18px;
    border-radius: 22px;
  }

  .hero-block h1 {
    font-size: 28px;
  }

  .stats-grid,
  .metadata-grid {
    grid-template-columns: 1fr;
  }

  .tab-strip {
    grid-template-columns: 1fr;
  }

  .field-block-wide {
    grid-column: span 1;
  }

  .panel-head {
    flex-direction: column;
  }
}
</style>
