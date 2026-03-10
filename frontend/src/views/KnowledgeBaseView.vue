<script setup lang="ts">
import { ref, onMounted } from 'vue';
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
}

interface Stats {
  total_chunks: number;
  total_documents: number;
}

type ToastType = 'success' | 'error';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const documents = ref<DocumentInfo[]>([]);
const stats = ref<Stats>({ total_chunks: 0, total_documents: 0 });
const loading = ref(false);
const uploading = ref(false);
const isDragOver = ref(false);
const toast = ref<{ visible: boolean; type: ToastType; message: string }>({
  visible: false,
  type: 'success',
  message: ''
});

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
    <section class="hero-block">
      <div>
        <div class="eyebrow">Knowledge Base</div>
        <h1>让知识库成为回答的底座</h1>
        <p>上传原始资料、沉淀索引结构、再在聊天页中获得带引用摘要的回答。</p>
      </div>
    </section>

    <section class="stats-grid">
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
          <div class="stat-label">文本分块</div>
        </div>
      </article>
    </section>

    <section class="panel-block">
      <div class="panel-head">
        <div>
          <div class="panel-title">上传文档</div>
          <div class="panel-subtitle">
            支持 PDF、Word、TXT、Markdown、CSV，单文件 20MB 以内。
          </div>
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
          accept=".pdf,.doc,.docx,.txt,.md,.rst,.csv"
          :disabled="uploading"
          @change="handleFileSelect" />
        <div class="upload-inner" v-if="!uploading">
          <UploadOutlined class="upload-icon" />
          <div class="upload-title">点击选择文件，或将文件拖放到这里</div>
          <div class="upload-hint">上传后会自动抽取文本并构建向量索引</div>
        </div>
        <div class="upload-inner" v-else>
          <LoadingOutlined class="upload-icon spin" />
          <div class="upload-title">正在处理文档并建立索引...</div>
          <div class="upload-hint">请稍候，完成后列表会自动刷新</div>
        </div>
      </label>
    </section>

    <section class="panel-block">
      <div class="panel-head">
        <div>
          <div class="panel-title">已收录文档</div>
          <div class="panel-subtitle">
            这里展示可被聊天问答检索到的文档资产。
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

      <div class="table-shell">
        <table class="docs-table">
          <thead>
            <tr>
              <th>文档名称</th>
              <th>上传时间</th>
              <th class="action-cell">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && documents.length === 0">
              <td colspan="3" class="empty-row">
                <LoadingOutlined class="spin" />
                正在加载文档列表...
              </td>
            </tr>
            <tr v-else-if="documents.length === 0">
              <td colspan="3" class="empty-row">暂无文档，请先上传文件。</td>
            </tr>
            <tr v-for="doc in documents" :key="doc.doc_id">
              <td>
                <div class="filename-cell">
                  <component
                    :is="getFileIcon(doc.filename)"
                    class="file-icon" />
                  <span class="filename-text">{{ doc.filename }}</span>
                </div>
              </td>
              <td class="upload-time">{{ formatDate(doc.upload_time) }}</td>
              <td class="action-cell">
                <button
                  class="delete-btn"
                  type="button"
                  @click="deleteDocument(doc)">
                  <DeleteOutlined />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
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
  max-width: 900px;
  margin: 0 auto;
  padding: 28px 0 64px;
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

.table-shell {
  overflow-x: auto;
}

.docs-table {
  width: 100%;
  border-collapse: collapse;
}

.docs-table th,
.docs-table td {
  padding: 16px 10px;
  border-bottom: 1px solid #f4f4f5;
  text-align: left;
}

.docs-table th {
  color: #71717a;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  color: #71717a;
  font-size: 18px;
}

.filename-text {
  color: #18181b;
  font-size: 14px;
  line-height: 1.6;
}

.upload-time {
  color: #71717a;
  font-size: 13px;
}

.action-cell {
  width: 80px;
  text-align: right;
}

.delete-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: transparent;
  color: #dc2626;
}

.delete-btn:hover {
  background: #fef2f2;
}

.empty-row {
  text-align: center !important;
  color: #a1a1aa;
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
  .hero-block,
  .panel-block {
    padding: 22px 18px;
    border-radius: 22px;
  }

  .hero-block h1 {
    font-size: 28px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
  }
}
</style>
