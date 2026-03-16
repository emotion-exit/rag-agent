<script setup lang="ts">
defineOptions({
  name: 'KnowledgeBaseView'
});

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FolderOpenOutlined,
  LoadingOutlined,
  PlusOutlined,
  ReloadOutlined,
  UploadOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import KnowledgeSpaceCreateModal from '@/components/knowledge-base/KnowledgeSpaceCreateModal.vue';
import KnowledgeBaseTaskProgressModal from '@/components/knowledge-base/KnowledgeBaseTaskProgressModal.vue';
import KnowledgeUploadModal from '@/components/knowledge-base/KnowledgeUploadModal.vue';
import UngroupedMigrationModal from '@/components/knowledge-base/UngroupedMigrationModal.vue';
import { buildPublicConfigHeaders } from '@/services/publicConfig';
import { getApiBase } from '@/services/runtime';
import type {
  DocumentInfo,
  KnowledgeBaseJobStatus,
  KnowledgeSpace,
  KnowledgeSpaceCreateForm,
  SpaceSummary,
  Stats,
  UploadForm,
  UploadSubmitPayload
} from '@/types/knowledgeBase';

interface KnowledgeBaseJobCreatedResponsePayload {
  job_id: string;
  status: string;
  message: string;
}

interface KnowledgeSpaceCreateResponsePayload {
  detail?: string;
  message?: string;
  space?: KnowledgeSpace;
}

type ToastType = 'success' | 'error';

const API_BASE = getApiBase();
const KNOWLEDGE_BASE_TASK_STORAGE_KEY = 'knowledge-base-active-task';
const CATEGORY_OPTIONS = [
  '制度规范',
  '操作手册',
  '常见问题',
  '方案资料',
  '报告分析',
  '会议纪要',
  '其他'
];

const spaces = ref<KnowledgeSpace[]>([]);
const documents = ref<DocumentInfo[]>([]);
const stats = ref<Stats>({ total_chunks: 0, total_documents: 0 });
const spaceSummary = ref<SpaceSummary>({
  total_spaces: 0,
  ungrouped_documents: 0
});
const selectedSpaceId = ref('');
const loading = ref(false);
const creatingSpace = ref(false);
const uploading = ref(false);
const migratingUngrouped = ref(false);
const createModalVisible = ref(false);
const uploadModalVisible = ref(false);
const migrationModalVisible = ref(false);
const taskProgressVisible = ref(false);
const currentTask = ref<KnowledgeBaseJobStatus | null>(null);
const toast = ref<{ visible: boolean; type: ToastType; message: string }>({
  visible: false,
  type: 'success',
  message: ''
});
let taskPollingTimer: number | null = null;

const createSpaceForm = ref<KnowledgeSpaceCreateForm>({
  name: '',
  parent_id: '',
  category: CATEGORY_OPTIONS[0] ?? '制度规范',
  topic: '',
  tags: '',
  version_label: '',
  description: ''
});

const uploadForm = ref<UploadForm>({
  tags: '',
  version_label: ''
});

function flattenSpaces(nodes: KnowledgeSpace[]): KnowledgeSpace[] {
  return nodes.flatMap((node) => [node, ...flattenSpaces(node.children || [])]);
}

const flatSpaces = computed(() => flattenSpaces(spaces.value));
const selectedSpace = computed(
  () =>
    flatSpaces.value.find((item) => item.space_id === selectedSpaceId.value) ||
    null
);
const childSpaces = computed(() =>
  flatSpaces.value.filter((item) => item.parent_id === selectedSpaceId.value)
);
const visibleDocuments = computed(() => {
  if (selectedSpaceId.value) {
    return documents.value.filter(
      (doc) => doc.space_id === selectedSpaceId.value
    );
  }

  return documents.value.filter((doc) => !String(doc.space_id || '').trim());
});
const ungroupedDocuments = computed(() =>
  documents.value.filter((doc) => !String(doc.space_id || '').trim())
);
const summaryItems = computed(() => [
  {
    label: '知识空间',
    value: `${spaceSummary.value.total_spaces} 个`,
    tone: 'neutral'
  },
  {
    label: '总文档',
    value: `${stats.value.total_documents} 篇`,
    tone: 'neutral'
  },
  {
    label: '文档分块',
    value: `${stats.value.total_chunks} 个`,
    tone: 'success'
  },
  {
    label: '未归类',
    value: `${spaceSummary.value.ungrouped_documents} 篇`,
    tone: 'warning'
  }
]);
const hasActiveTask = computed(
  () =>
    currentTask.value?.status === 'queued' ||
    currentTask.value?.status === 'running'
);
const documentPanelTitle = computed(() =>
  selectedSpace.value ? `${selectedSpace.value.name} 的直属文档` : '未归类文档'
);
const documentPanelSubtitle = computed(() =>
  selectedSpace.value
    ? '当前列表仅展示所选空间的直属文档，继续下钻请点击子空间。'
    : '这里只显示历史遗留的未归类文档，建议逐步迁移到正式空间。'
);

function buildDefaultCreateSpaceForm(parentId = ''): KnowledgeSpaceCreateForm {
  return {
    name: '',
    parent_id: parentId,
    category: CATEGORY_OPTIONS[0] ?? '制度规范',
    topic: '',
    tags: '',
    version_label: '',
    description: ''
  };
}

function showToast(message: string, type: ToastType = 'success') {
  toast.value = { visible: true, type, message };
  window.setTimeout(() => {
    toast.value.visible = false;
  }, 2800);
}

function clearTaskPollingTimer() {
  if (taskPollingTimer !== null) {
    window.clearTimeout(taskPollingTimer);
    taskPollingTimer = null;
  }
}

function persistTaskSnapshot(task: KnowledgeBaseJobStatus | null) {
  if (!task) {
    window.localStorage.removeItem(KNOWLEDGE_BASE_TASK_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(
    KNOWLEDGE_BASE_TASK_STORAGE_KEY,
    JSON.stringify(task)
  );
}

function readPersistedTaskSnapshot() {
  const rawValue = window.localStorage.getItem(KNOWLEDGE_BASE_TASK_STORAGE_KEY);
  if (!rawValue) return null;

  try {
    return JSON.parse(rawValue) as KnowledgeBaseJobStatus;
  } catch {
    window.localStorage.removeItem(KNOWLEDGE_BASE_TASK_STORAGE_KEY);
    return null;
  }
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

function formatTagList(value: string) {
  return String(value || '')
    .split(/[，,、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatImageCount(value: number) {
  return value > 0 ? `附图 ${value} 张` : '无附图';
}

function formatChunkCount(value: number) {
  return `${value || 0} 个分块`;
}

async function parseApiResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return { detail: text.trim() };
}

function extractApiErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === 'object') {
    const detail = Reflect.get(payload, 'detail');
    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim();
    }

    const message = Reflect.get(payload, 'message');
    if (typeof message === 'string' && message.trim()) {
      return message.trim();
    }
  }

  return `HTTP ${status}`;
}

function syncSelectedSpace(preferredSpaceId = '') {
  const availableIds = new Set(flatSpaces.value.map((item) => item.space_id));

  if (preferredSpaceId && availableIds.has(preferredSpaceId)) {
    selectedSpaceId.value = preferredSpaceId;
    return;
  }

  if (selectedSpaceId.value && availableIds.has(selectedSpaceId.value)) {
    return;
  }

  selectedSpaceId.value = flatSpaces.value[0]?.space_id || '';
}

async function refreshKnowledgeBase(preferredSpaceId = '') {
  loading.value = true;
  try {
    const [spacesRes, docsRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/api/knowledge-base/spaces`, {
        headers: buildPublicConfigHeaders()
      }),
      fetch(`${API_BASE}/api/knowledge-base/documents`, {
        headers: buildPublicConfigHeaders()
      }),
      fetch(`${API_BASE}/api/knowledge-base/stats`, {
        headers: buildPublicConfigHeaders()
      })
    ]);

    if (!spacesRes.ok) throw new Error(`HTTP ${spacesRes.status}`);
    if (!docsRes.ok) throw new Error(`HTTP ${docsRes.status}`);
    if (!statsRes.ok) throw new Error(`HTTP ${statsRes.status}`);

    const spacesData = (await spacesRes.json()) as {
      spaces?: KnowledgeSpace[];
      summary?: SpaceSummary;
    };
    const docsData = await docsRes.json();
    const statsData = (await statsRes.json()) as Stats;

    spaces.value = Array.isArray(spacesData.spaces) ? spacesData.spaces : [];
    documents.value = Array.isArray(docsData.documents)
      ? docsData.documents
      : [];
    stats.value = statsData;
    spaceSummary.value = {
      total_spaces: Number(spacesData.summary?.total_spaces || 0),
      ungrouped_documents: Number(spacesData.summary?.ungrouped_documents || 0)
    };
    syncSelectedSpace(preferredSpaceId);
  } catch {
    showToast('加载知识空间失败，请检查后端服务是否正常运行', 'error');
  } finally {
    loading.value = false;
  }
}

function validateCreateSpaceForm(payload: KnowledgeSpaceCreateForm) {
  if (!payload.name.trim()) {
    showToast('请先填写知识空间名称', 'error');
    return false;
  }

  if (!payload.category.trim()) {
    showToast('请先填写知识空间分类', 'error');
    return false;
  }

  if (!payload.topic.trim()) {
    showToast('请先填写知识空间主题', 'error');
    return false;
  }

  return true;
}

function openCreateSpaceModal(parentId = '') {
  createSpaceForm.value = buildDefaultCreateSpaceForm(parentId);
  createModalVisible.value = true;
}

function closeCreateSpaceModal() {
  if (creatingSpace.value) return;
  createModalVisible.value = false;
}

async function createSpace(payload: KnowledgeSpaceCreateForm) {
  if (creatingSpace.value || !validateCreateSpaceForm(payload)) return;

  creatingSpace.value = true;
  try {
    const response = await fetch(`${API_BASE}/api/knowledge-base/spaces`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildPublicConfigHeaders()
      },
      body: JSON.stringify({
        name: payload.name.trim(),
        parent_id: payload.parent_id.trim(),
        category: payload.category.trim(),
        topic: payload.topic.trim(),
        tags: payload.tags.trim(),
        version_label: payload.version_label.trim(),
        description: payload.description.trim()
      })
    });

    const data = (await parseApiResponse(
      response
    )) as KnowledgeSpaceCreateResponsePayload;
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    const createdSpaceId = data.space?.space_id || '';
    await refreshKnowledgeBase(createdSpaceId);
    createSpaceForm.value = buildDefaultCreateSpaceForm();
    createModalVisible.value = false;
    showToast(data.message || '知识空间创建成功');
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`创建知识空间失败：${errMsg}`, 'error');
  } finally {
    creatingSpace.value = false;
  }
}

function openUploadModal() {
  if (hasActiveTask.value) {
    taskProgressVisible.value = true;
    showToast('当前已有知识库任务正在执行，请先等待完成', 'error');
    return;
  }

  if (!selectedSpace.value) {
    showToast('请先选择知识空间，再上传文档', 'error');
    return;
  }

  uploadModalVisible.value = true;
}

function closeUploadModal() {
  if (uploading.value) return;
  uploadModalVisible.value = false;
}

function openMigrationModal() {
  if (hasActiveTask.value) {
    taskProgressVisible.value = true;
    showToast('当前已有知识库任务正在执行，请先等待完成', 'error');
    return;
  }

  if (spaceSummary.value.ungrouped_documents === 0) {
    showToast('当前没有未归类文档可迁移', 'error');
    return;
  }

  if (flatSpaces.value.length === 0) {
    showToast('请先创建目标知识空间，再执行迁移', 'error');
    return;
  }

  migrationModalVisible.value = true;
}

function closeMigrationModal() {
  if (migratingUngrouped.value) return;
  migrationModalVisible.value = false;
}

function closeTaskProgressModal() {
  if (hasActiveTask.value) return;
  taskProgressVisible.value = false;
  persistTaskSnapshot(null);
  currentTask.value = null;
}

async function fetchKnowledgeBaseJob(jobId: string) {
  const response = await fetch(`${API_BASE}/api/knowledge-base/jobs/${jobId}`, {
    headers: buildPublicConfigHeaders()
  });
  const data = (await parseApiResponse(response)) as KnowledgeBaseJobStatus;
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(data, response.status));
  }
  return data;
}

async function trackKnowledgeBaseJob(jobId: string) {
  clearTaskPollingTimer();

  const poll = async () => {
    try {
      const job = await fetchKnowledgeBaseJob(jobId);
      currentTask.value = job;
      persistTaskSnapshot(job);

      if (job.status === 'queued' || job.status === 'running') {
        taskPollingTimer = window.setTimeout(poll, 1200);
        return;
      }

      clearTaskPollingTimer();
      uploading.value = false;
      migratingUngrouped.value = false;

      const resultSpaceId = String(
        job.result?.space_id || selectedSpaceId.value || ''
      );
      await refreshKnowledgeBase(resultSpaceId);
      uploadModalVisible.value = false;
      migrationModalVisible.value = false;

      if (job.status === 'completed') {
        uploadForm.value = { tags: '', version_label: '' };
        showToast(job.message || '知识库任务已完成');
      } else {
        showToast(
          job.error_message || job.message || '知识库任务执行失败',
          'error'
        );
      }
    } catch (err: unknown) {
      clearTaskPollingTimer();
      uploading.value = false;
      migratingUngrouped.value = false;
      const errMsg = err instanceof Error ? err.message : String(err);
      showToast(`获取任务进度失败：${errMsg}`, 'error');
    }
  };

  taskProgressVisible.value = true;
  await poll();
}

async function restorePersistedKnowledgeBaseTask() {
  const persistedTask = readPersistedTaskSnapshot();
  if (!persistedTask?.job_id) return;

  currentTask.value = persistedTask;
  taskProgressVisible.value = true;

  try {
    await trackKnowledgeBaseJob(persistedTask.job_id);
  } catch {
    persistTaskSnapshot(null);
  }
}

async function handleUploadSubmit(payload: UploadSubmitPayload) {
  if (uploading.value || hasActiveTask.value || !selectedSpace.value) return;

  uploading.value = true;
  try {
    const formData = new FormData();
    for (const file of payload.files) {
      formData.append('files', file);
    }
    formData.append('space_id', selectedSpace.value.space_id);
    formData.append('tags', payload.tags.trim());
    formData.append('version_label', payload.version_label.trim());

    const response = await fetch(`${API_BASE}/api/knowledge-base/upload-jobs`, {
      method: 'POST',
      headers: buildPublicConfigHeaders(),
      body: formData
    });
    const data = (await parseApiResponse(
      response
    )) as KnowledgeBaseJobCreatedResponsePayload;
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    currentTask.value = {
      job_id: data.job_id,
      job_type: 'upload',
      status: 'queued',
      message: data.message || '上传任务已创建',
      error_message: '',
      current_document: '',
      total_documents: payload.files.length,
      processed_documents: 0,
      total_chunks: 0,
      processed_chunks: 0,
      created_at: '',
      updated_at: '',
      result: {
        space_id: selectedSpace.value.space_id
      }
    };
    persistTaskSnapshot(currentTask.value);
    await trackKnowledgeBaseJob(data.job_id);
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`上传失败：${errMsg}`, 'error');
    uploading.value = false;
  }
}

async function handleUngroupedMigration(targetSpaceId: string) {
  if (migratingUngrouped.value || hasActiveTask.value) return;

  migratingUngrouped.value = true;
  try {
    const response = await fetch(
      `${API_BASE}/api/knowledge-base/documents/migrate-ungrouped/jobs`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...buildPublicConfigHeaders()
        },
        body: JSON.stringify({ target_space_id: targetSpaceId })
      }
    );
    const data = (await parseApiResponse(
      response
    )) as KnowledgeBaseJobCreatedResponsePayload;
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    currentTask.value = {
      job_id: data.job_id,
      job_type: 'migrate_ungrouped',
      status: 'queued',
      message: data.message || '迁移任务已创建',
      error_message: '',
      current_document: '',
      total_documents: ungroupedDocuments.value.length,
      processed_documents: 0,
      total_chunks: ungroupedDocuments.value.reduce(
        (sum, item) => sum + Number(item.chunk_count || 0),
        0
      ),
      processed_chunks: 0,
      created_at: '',
      updated_at: '',
      result: {
        space_id: targetSpaceId
      }
    };
    persistTaskSnapshot(currentTask.value);
    await trackKnowledgeBaseJob(data.job_id);
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`迁移失败：${errMsg}`, 'error');
    migratingUngrouped.value = false;
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
        method: 'DELETE',
        headers: buildPublicConfigHeaders()
      }
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    showToast(`已删除文档“${doc.filename}”`);
    await refreshKnowledgeBase(selectedSpace.value?.space_id || '');
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除失败：${errMsg}`, 'error');
  }
}

function selectSpace(spaceId: string) {
  selectedSpaceId.value = spaceId;
}

function assignSelectedSpaceAsParent() {
  openCreateSpaceModal(selectedSpace.value?.space_id || '');
}

onMounted(() => {
  refreshKnowledgeBase();
  restorePersistedKnowledgeBaseTask();
});

onBeforeUnmount(() => {
  clearTaskPollingTimer();
});
</script>

<template>
  <div class="kb-page">
    <section class="kb-panel kb-hero">
      <div class="kb-hero-head">
        <div>
          <div class="kb-eyebrow">Knowledge Space</div>
          <h1 class="kb-title">知识空间浏览</h1>
          <p class="kb-subtitle">
            页面只保留浏览、下钻和当前空间操作。创建空间、上传文件都改为弹窗处理，避免主界面堆叠表单。
          </p>
        </div>
        <div class="kb-hero-actions">
          <button
            v-if="spaceSummary.ungrouped_documents > 0"
            type="button"
            class="kb-btn kb-btn-warning"
            :disabled="hasActiveTask"
            @click="openMigrationModal">
            <WarningOutlined />
            迁移未归类文档
          </button>
          <button
            type="button"
            class="kb-btn kb-btn-secondary"
            :disabled="hasActiveTask"
            @click="openCreateSpaceModal()">
            <PlusOutlined />
            新建空间
          </button>
          <button
            type="button"
            class="kb-btn kb-btn-primary"
            :disabled="!selectedSpace || hasActiveTask"
            @click="openUploadModal">
            <UploadOutlined />
            上传文档
          </button>
          <button
            type="button"
            class="kb-btn kb-btn-ghost"
            :disabled="loading"
            @click="refreshKnowledgeBase(selectedSpaceId)">
            <ReloadOutlined :class="{ spin: loading }" />
            刷新
          </button>
        </div>
      </div>

      <div class="kb-summary-grid">
        <article
          v-for="item in summaryItems"
          :key="item.label"
          :class="['kb-summary-card', `kb-summary-card-${item.tone}`]">
          <div class="kb-summary-label">{{ item.label }}</div>
          <div class="kb-summary-value">{{ item.value }}</div>
        </article>
      </div>
    </section>

    <section class="kb-layout">
      <aside class="kb-panel kb-sidebar">
        <div class="kb-section-head">
          <div>
            <div class="kb-section-title">空间树</div>
            <div class="kb-section-desc">像目录一样浏览知识空间。</div>
          </div>
          <button
            v-if="selectedSpace"
            type="button"
            class="kb-chip-btn"
            :disabled="hasActiveTask"
            @click="assignSelectedSpaceAsParent">
            <PlusOutlined />
            子空间
          </button>
        </div>

        <div class="kb-tree-list">
          <button
            type="button"
            :class="[
              'kb-tree-item',
              !selectedSpaceId ? 'kb-tree-item-active' : ''
            ]"
            @click="selectedSpaceId = ''">
            <div class="kb-tree-main">
              <FolderOpenOutlined class="kb-tree-icon" />
              <div class="kb-tree-copy">
                <div class="kb-tree-name">未归类文档</div>
                <div class="kb-tree-path">旧数据过渡区，不建议继续上传</div>
              </div>
            </div>
            <span class="kb-tree-count">
              {{ spaceSummary.ungrouped_documents }}
            </span>
          </button>

          <div v-if="flatSpaces.length === 0" class="kb-empty kb-empty-tree">
            <FolderOpenOutlined class="kb-empty-icon" />
            <p>还没有知识空间，请先创建一个顶级空间。</p>
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              @click="openCreateSpaceModal()">
              <PlusOutlined />
              创建第一个空间
            </button>
          </div>

          <button
            v-for="space in flatSpaces"
            :key="space.space_id"
            type="button"
            :class="[
              'kb-tree-item',
              selectedSpaceId === space.space_id ? 'kb-tree-item-active' : ''
            ]"
            :style="{ paddingLeft: `${16 + space.depth * 18}px` }"
            @click="selectSpace(space.space_id)">
            <div class="kb-tree-main">
              <FolderOpenOutlined class="kb-tree-icon" />
              <div class="kb-tree-copy">
                <div class="kb-tree-name">{{ space.name }}</div>
                <div class="kb-tree-path">{{ space.path }}</div>
              </div>
            </div>
            <span class="kb-tree-count">
              {{ space.direct_document_count }}/{{ space.total_document_count }}
            </span>
          </button>
        </div>
      </aside>

      <div class="kb-main">
        <article class="kb-panel kb-focus-panel">
          <div class="kb-section-head kb-focus-head">
            <div>
              <div class="kb-section-title">
                {{ selectedSpace ? selectedSpace.name : '未归类文档' }}
              </div>
              <div class="kb-section-desc">
                {{ selectedSpace ? selectedSpace.path : '历史遗留数据过渡区' }}
              </div>
            </div>
            <div class="kb-focus-actions">
              <button
                v-if="selectedSpace"
                type="button"
                class="kb-btn kb-btn-secondary"
                :disabled="hasActiveTask"
                @click="assignSelectedSpaceAsParent">
                <PlusOutlined />
                新建子空间
              </button>
              <button
                type="button"
                class="kb-btn kb-btn-primary"
                :disabled="!selectedSpace || hasActiveTask"
                @click="openUploadModal">
                <UploadOutlined />
                上传到当前空间
              </button>
            </div>
          </div>

          <template v-if="selectedSpace">
            <div class="kb-focus-stats">
              <div class="kb-focus-stat">
                <span class="kb-focus-stat-label">直属文档</span>
                <strong class="kb-focus-stat-value">
                  {{ selectedSpace.direct_document_count }}
                </strong>
              </div>
              <div class="kb-focus-stat">
                <span class="kb-focus-stat-label">全部文档</span>
                <strong class="kb-focus-stat-value">
                  {{ selectedSpace.total_document_count }}
                </strong>
              </div>
              <div class="kb-focus-stat">
                <span class="kb-focus-stat-label">子空间</span>
                <strong class="kb-focus-stat-value">
                  {{ selectedSpace.child_count }}
                </strong>
              </div>
              <div class="kb-focus-stat">
                <span class="kb-focus-stat-label">创建时间</span>
                <strong class="kb-focus-stat-value kb-focus-stat-time">
                  {{ formatDate(selectedSpace.created_at) }}
                </strong>
              </div>
            </div>

            <div class="kb-meta-row">
              <span class="kb-meta-chip">
                分类 · {{ formatMetadata(selectedSpace.category) }}
              </span>
              <span class="kb-meta-chip">
                主题 · {{ formatMetadata(selectedSpace.topic) }}
              </span>
              <span
                v-if="selectedSpace.version_label"
                class="kb-meta-chip kb-meta-chip-success">
                版本 · {{ selectedSpace.version_label }}
              </span>
              <span
                v-for="tag in formatTagList(selectedSpace.tags)"
                :key="`${selectedSpace.space_id}-${tag}`"
                class="kb-meta-chip">
                {{ tag }}
              </span>
            </div>

            <p class="kb-focus-description">
              {{ selectedSpace.description || '当前空间未填写额外说明。' }}
            </p>

            <div v-if="childSpaces.length > 0" class="kb-children-wrap">
              <div class="kb-children-title">下一级空间</div>
              <div class="kb-children-grid">
                <button
                  v-for="space in childSpaces"
                  :key="space.space_id"
                  type="button"
                  class="kb-child-card"
                  @click="selectSpace(space.space_id)">
                  <div class="kb-child-name">{{ space.name }}</div>
                  <div class="kb-child-path">{{ space.path }}</div>
                  <div class="kb-child-meta">
                    {{ space.child_count }} 个子空间 ·
                    {{ space.total_document_count }} 篇文档
                  </div>
                </button>
              </div>
            </div>
          </template>

          <div v-else class="kb-empty kb-empty-focus kb-empty-warning">
            <DatabaseOutlined class="kb-empty-icon" />
            <p>
              当前是未归类视图。建议先创建正式知识空间，再通过弹窗上传文档。
            </p>
            <button
              v-if="spaceSummary.ungrouped_documents > 0"
              type="button"
              class="kb-btn kb-btn-warning"
              :disabled="hasActiveTask"
              @click="openMigrationModal">
              <WarningOutlined />
              批量迁移并重建索引
            </button>
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              :disabled="hasActiveTask"
              @click="openCreateSpaceModal()">
              <PlusOutlined />
              新建顶级空间
            </button>
          </div>
        </article>

        <article class="kb-panel kb-docs-panel">
          <div class="kb-section-head">
            <div>
              <div class="kb-section-title">{{ documentPanelTitle }}</div>
              <div class="kb-section-desc">{{ documentPanelSubtitle }}</div>
            </div>
            <div class="kb-doc-count">{{ visibleDocuments.length }} 篇</div>
          </div>

          <div
            v-if="!selectedSpace && ungroupedDocuments.length > 0"
            class="kb-alert-banner kb-alert-banner-warning">
            <div>
              <div class="kb-alert-title">迁移时会重新 embedding</div>
              <div class="kb-alert-text">
                批量迁移会把目标空间的元数据重新写入这些文档，并重建对应向量索引，请尽量在低峰时段操作。
              </div>
            </div>
            <button
              type="button"
              class="kb-btn kb-btn-warning"
              :disabled="hasActiveTask"
              @click="openMigrationModal">
              <WarningOutlined />
              立即迁移
            </button>
          </div>

          <div v-if="loading && documents.length === 0" class="kb-empty">
            <LoadingOutlined class="spin kb-empty-icon" />
            <p>正在加载文档列表...</p>
          </div>
          <div v-else-if="visibleDocuments.length === 0" class="kb-empty">
            <DatabaseOutlined class="kb-empty-icon" />
            <p>
              {{
                selectedSpace
                  ? '当前空间还没有直属文档，可以先上传文件，或进入子空间继续查看。'
                  : '暂无未归类文档。'
              }}
            </p>
          </div>
          <div v-else class="kb-doc-grid">
            <TransitionGroup name="list">
              <article
                v-for="doc in visibleDocuments"
                :key="doc.doc_id"
                class="kb-doc-card">
                <div class="kb-doc-head">
                  <div class="kb-doc-title-wrap">
                    <div class="kb-doc-icon-box">
                      <component
                        :is="getFileIcon(doc.filename)"
                        class="kb-doc-icon" />
                    </div>
                    <h3 class="kb-doc-title" :title="doc.filename">
                      {{ doc.filename }}
                    </h3>
                  </div>
                  <button
                    class="kb-icon-btn kb-icon-btn-danger"
                    type="button"
                    title="删除文档"
                    @click="deleteDocument(doc)">
                    <DeleteOutlined />
                  </button>
                </div>

                <div class="kb-doc-tags">
                  <span class="kb-doc-tag">
                    {{ formatMetadata(doc.category) }}
                  </span>
                  <span class="kb-doc-tag">
                    {{ formatMetadata(doc.knowledge_space) }}
                  </span>
                  <span v-if="doc.topic" class="kb-doc-tag">
                    {{ doc.topic }}
                  </span>
                  <template v-if="doc.tags">
                    <span
                      v-for="tag in formatTagList(doc.tags)"
                      :key="`${doc.doc_id}-${tag}`"
                      class="kb-doc-tag">
                      {{ tag }}
                    </span>
                  </template>
                  <span
                    v-if="doc.version_label"
                    class="kb-doc-tag kb-doc-tag-success">
                    {{ doc.version_label }}
                  </span>
                </div>

                <div class="kb-doc-footer">
                  <div class="kb-doc-meta-item">
                    <span class="kb-doc-meta-label">上传于</span>
                    <span class="kb-doc-meta-value">
                      {{ formatDate(doc.upload_time) }}
                    </span>
                  </div>
                  <div class="kb-doc-meta-item">
                    <span class="kb-doc-badge">
                      {{ formatChunkCount(doc.chunk_count) }}
                    </span>
                  </div>
                  <div class="kb-doc-meta-item">
                    <span
                      :class="[
                        'kb-doc-badge',
                        doc.image_count > 0
                          ? 'kb-doc-badge-success'
                          : 'kb-doc-badge-muted'
                      ]">
                      {{ formatImageCount(doc.image_count) }}
                    </span>
                  </div>
                </div>
              </article>
            </TransitionGroup>
          </div>
        </article>
      </div>
    </section>

    <Transition name="toast">
      <div v-if="toast.visible" :class="['kb-toast', `kb-toast-${toast.type}`]">
        <CheckCircleOutlined v-if="toast.type === 'success'" />
        <WarningOutlined v-else />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>

    <KnowledgeSpaceCreateModal
      :visible="createModalVisible"
      :submitting="creatingSpace"
      :spaces="flatSpaces"
      :category-options="CATEGORY_OPTIONS"
      :initial-form="createSpaceForm"
      @close="closeCreateSpaceModal"
      @submit="createSpace" />

    <KnowledgeUploadModal
      :visible="uploadModalVisible"
      :submitting="uploading"
      :selected-space="selectedSpace"
      :initial-form="uploadForm"
      @close="closeUploadModal"
      @submit="handleUploadSubmit" />

    <UngroupedMigrationModal
      :visible="migrationModalVisible"
      :submitting="migratingUngrouped"
      :spaces="flatSpaces"
      :ungrouped-documents="ungroupedDocuments"
      @close="closeMigrationModal"
      @submit="handleUngroupedMigration" />

    <KnowledgeBaseTaskProgressModal
      :visible="taskProgressVisible"
      :task="currentTask"
      @close="closeTaskProgressModal" />
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding-top: 16px;
  padding-bottom: 18px;
}

.kb-panel {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(24, 24, 27, 0.06);
  box-shadow: 0 20px 50px rgba(24, 24, 27, 0.04);
  border-radius: 22px;
  padding: 22px;
}

.kb-hero {
  margin-bottom: 0;
}

.kb-hero-head,
.kb-section-head,
.kb-doc-head,
.kb-doc-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.kb-eyebrow {
  color: #71717a;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.kb-title {
  margin-top: 0;
  color: #18181b;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}

.kb-subtitle,
.kb-section-desc,
.kb-tree-path,
.kb-focus-description,
.kb-child-path,
.kb-child-meta,
.kb-doc-meta-label,
.kb-doc-meta-value {
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.kb-subtitle {
  max-width: 680px;
  margin-top: 10px;
}

.kb-hero-actions,
.kb-focus-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.kb-btn,
.kb-chip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: none;
  border-radius: 12px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.kb-btn:hover,
.kb-chip-btn:hover {
  transform: translateY(-1px);
}

.kb-btn:disabled,
.kb-chip-btn:disabled,
.kb-icon-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.kb-btn-primary {
  background: linear-gradient(135deg, #18181b, #27272a);
  color: #ffffff;
  box-shadow: 0 18px 36px rgba(24, 24, 27, 0.16);
}

.kb-btn-warning {
  background: #f4f4f5;
  color: #3f3f46;
}

.kb-btn-secondary,
.kb-chip-btn {
  background: #f4f4f5;
  color: #3f3f46;
}

.kb-btn-ghost {
  background: #f4f4f5;
  color: #3f3f46;
}

.kb-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.kb-summary-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(24, 24, 27, 0.08);
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
}

.kb-summary-card-success {
  border-color: rgba(24, 24, 27, 0.08);
}

.kb-summary-card-warning {
  border-color: rgba(24, 24, 27, 0.08);
}

.kb-summary-card-success .kb-summary-value {
  color: var(--color-success-strong);
}

.kb-summary-card-warning .kb-summary-value {
  color: var(--color-warning-strong);
}

.kb-summary-label,
.kb-focus-stat-label {
  color: #71717a;
  font-size: 12px;
}

.kb-summary-value,
.kb-focus-stat-value,
.kb-tree-name,
.kb-child-name,
.kb-doc-title,
.kb-section-title {
  color: #18181b;
  font-weight: 700;
}

.kb-summary-value {
  margin-top: 8px;
  font-size: 18px;
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.kb-sidebar,
.kb-main {
  min-width: 0;
}

.kb-main {
  display: grid;
  gap: 16px;
}

.kb-tree-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kb-tree-item {
  width: 100%;
  border: 1px solid rgba(24, 24, 27, 0.08);
  border-radius: 18px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.kb-tree-item:hover {
  transform: translateY(-1px);
  border-color: rgba(24, 24, 27, 0.14);
}

.kb-tree-item-active {
  border-color: transparent;
  background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
  box-shadow: 0 18px 36px rgba(24, 24, 27, 0.16);
}

.kb-tree-item-active .kb-tree-name,
.kb-tree-item-active .kb-tree-path,
.kb-tree-item-active .kb-tree-count,
.kb-tree-item-active .kb-tree-icon {
  color: #ffffff;
}

.kb-tree-item-active .kb-tree-count {
  background: rgba(255, 255, 255, 0.12);
  border-color: transparent;
}

.kb-tree-main,
.kb-doc-title-wrap {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.kb-tree-icon,
.kb-doc-icon {
  flex-shrink: 0;
}

.kb-tree-icon {
  margin-top: 2px;
  color: #71717a;
}

.kb-tree-copy {
  min-width: 0;
}

.kb-tree-path {
  margin-top: 4px;
  word-break: break-word;
}

.kb-tree-count,
.kb-doc-count {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 6px 10px;
  background: #f4f4f5;
  border: 1px solid rgba(24, 24, 27, 0.08);
  color: #52525b;
  font-size: 12px;
  font-weight: 700;
}

.kb-doc-count {
  color: #18181b;
}

.kb-focus-head {
  margin-bottom: 18px;
}

.kb-focus-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kb-focus-stat {
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
  border: 1px solid rgba(24, 24, 27, 0.08);
}

.kb-focus-stat-value {
  display: block;
  margin-top: 6px;
  font-size: 20px;
}

.kb-focus-stat-time {
  font-size: 14px;
  line-height: 1.5;
}

.kb-meta-row,
.kb-doc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kb-meta-row {
  margin-top: 16px;
}

.kb-meta-chip,
.kb-doc-tag {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f4f4f5;
  color: #52525b;
  font-size: 12px;
  font-weight: 600;
}

.kb-meta-chip-success,
.kb-doc-tag-success,
.kb-doc-badge-success {
  background: rgba(37, 99, 65, 0.12);
  color: #1f6b42;
}

.kb-focus-description {
  margin-top: 16px;
}

.kb-children-wrap {
  margin-top: 20px;
}

.kb-children-title {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.kb-children-grid,
.kb-doc-grid {
  display: grid;
  gap: 12px;
}

.kb-children-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  margin-top: 10px;
}

.kb-child-card,
.kb-doc-card {
  border: 1px solid rgba(24, 24, 27, 0.08);
  border-radius: 18px;
  background: linear-gradient(180deg, #fcfcfd 0%, #f5f5f5 100%);
}

.kb-child-card {
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.kb-child-card:hover {
  transform: translateY(-2px);
  border-color: rgba(24, 24, 27, 0.14);
  box-shadow: 0 12px 24px rgba(24, 24, 27, 0.06);
}

.kb-child-path,
.kb-child-meta {
  margin-top: 6px;
}

.kb-doc-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.kb-doc-card {
  padding: 18px;
}

.kb-doc-head {
  align-items: center;
}

.kb-doc-icon-box {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: #f4f4f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kb-doc-icon {
  font-size: 18px;
  color: #52525b;
}

.kb-doc-title {
  font-size: 15px;
  line-height: 1.5;
  word-break: break-word;
}

.kb-icon-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #a1a1aa;
  cursor: pointer;
}

.kb-icon-btn-danger {
  background: transparent;
  color: #9e3328;
}

.kb-doc-tags {
  margin-top: 14px;
}

.kb-doc-footer {
  margin-top: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.kb-doc-meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-doc-badge,
.kb-doc-badge-muted {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f4f4f5;
  color: #52525b;
  font-size: 12px;
  font-weight: 600;
}

.kb-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 42px 20px;
  border-radius: 18px;
  border: 1px dashed rgba(24, 24, 27, 0.12);
  background: rgba(250, 250, 250, 0.5);
  color: #71717a;
  text-align: center;
}

.kb-empty-tree {
  margin-top: 4px;
}

.kb-empty-focus {
  padding: 32px 20px;
}

.kb-empty-warning {
  background: rgba(250, 250, 250, 0.5);
  border-color: rgba(24, 24, 27, 0.12);
}

.kb-alert-banner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(24, 24, 27, 0.08);
  background: rgba(180, 125, 29, 0.12);
}

.kb-alert-banner-warning {
  border-color: transparent;
}

.kb-alert-title {
  color: #9f670f;
  font-size: 14px;
  font-weight: 700;
}

.kb-alert-text {
  margin-top: 4px;
  color: #71717a;
  font-size: 13px;
  line-height: 1.6;
}

.kb-empty-icon {
  margin-bottom: 12px;
  font-size: 30px;
  color: #a1a1aa;
}

.kb-toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 190;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 16px;
  border-radius: 999px;
  box-shadow: var(--shadow-floating);
  font-size: 13px;
  font-weight: 600;
}

.kb-toast-success {
  background: var(--color-surface);
  color: var(--color-heading);
  border: 1px solid var(--color-border);
}

.kb-toast-error {
  background: var(--color-surface);
  color: var(--color-danger);
  border: 1px solid var(--color-danger-border);
}

.toast-enter-active,
.toast-leave-active,
.list-enter-active,
.list-leave-active {
  transition: all 0.24s ease;
}

.toast-enter-from,
.toast-leave-to,
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1024px) {
  .kb-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-summary-grid,
  .kb-focus-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kb-page {
    padding-top: 12px;
    padding-bottom: 16px;
  }

  .kb-panel {
    padding: 16px;
    border-radius: 18px;
  }

  .kb-hero-head,
  .kb-section-head,
  .kb-doc-head,
  .kb-doc-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .kb-hero-actions,
  .kb-focus-actions {
    justify-content: flex-start;
  }

  .kb-btn,
  .kb-chip-btn {
    width: 100%;
  }

  .kb-alert-banner {
    flex-direction: column;
  }

  .kb-summary-grid,
  .kb-focus-stats,
  .kb-doc-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-toast {
    right: 14px;
    left: 14px;
    bottom: 14px;
    justify-content: center;
  }
}
</style>
