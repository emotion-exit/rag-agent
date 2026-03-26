<script setup lang="ts">
defineOptions({
  name: 'KnowledgeBaseView'
});

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FileWordOutlined,
  LoadingOutlined,
  PlusOutlined,
  ReloadOutlined,
  UploadOutlined
} from '@ant-design/icons-vue';
import KnowledgeSpaceCreateModal from '@/components/knowledge-base/KnowledgeSpaceCreateModal.vue';
import KnowledgeDangerConfirmModal from '@/components/knowledge-base/KnowledgeDangerConfirmModal.vue';
import KnowledgeBaseTaskProgressModal from '@/components/knowledge-base/KnowledgeBaseTaskProgressModal.vue';
import KnowledgeUploadModal from '@/components/knowledge-base/KnowledgeUploadModal.vue';
import {
  OBadge,
  OButton,
  OCard,
  OEmptyState,
  OPanelRow,
  useOToast
} from '@/orange-ui';
import { isAdminUser, useAuthState } from '@/services/auth';
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
  message?: string;
}

interface KnowledgeSpaceMutationResponsePayload {
  detail?: string;
  message?: string;
  space?: KnowledgeSpace;
}

interface DangerImpactStat {
  label: string;
  value: string;
  kind?: 'metric' | 'context';
}

type DangerActionType = 'delete-space' | 'delete-document';

interface DangerConfirmState {
  visible: boolean;
  action: DangerActionType | null;
  targetId: string;
  title: string;
  message: string;
  confirmText: string;
  impactStats: DangerImpactStat[];
  impactItems: string[];
}

const KNOWLEDGE_BASE_TASK_STORAGE_KEY = 'knowledge-base-active-task';

const spaces = ref<KnowledgeSpace[]>([]);
const documents = ref<DocumentInfo[]>([]);
const stats = ref<Stats>({ total_chunks: 0, total_documents: 0 });
const spaceSummary = ref<SpaceSummary>({
  total_spaces: 0,
  total_documents: 0,
  ungrouped_documents: 0
});
const selectedSpaceId = ref('');
const loading = ref(false);
const submittingSpace = ref(false);
const deletingSpace = ref(false);
const deletingDocumentId = ref('');
const uploading = ref(false);
const createModalVisible = ref(false);
const createModalMode = ref<'create' | 'edit'>('create');
const uploadModalVisible = ref(false);
const taskProgressVisible = ref(false);
const currentTask = ref<KnowledgeBaseJobStatus | null>(null);
const createSpaceForm = ref<KnowledgeSpaceCreateForm>({
  name: '',
  tags: '',
  description: '',
  visibility: 'private'
});
const uploadForm = ref<UploadForm>({
  tags: ''
});
const dangerConfirm = ref<DangerConfirmState>({
  visible: false,
  action: null,
  targetId: '',
  title: '',
  message: '',
  confirmText: '',
  impactStats: [],
  impactItems: []
});
const oToast = useOToast();
const authState = useAuthState();
let taskPollingTimer: number | null = null;

const selectedSpace = computed(
  () =>
    spaces.value.find((item) => item.space_id === selectedSpaceId.value) || null
);
const visibleDocuments = computed(() => {
  if (!selectedSpace.value) return [];
  return documents.value.filter(
    (doc) => doc.space_id === selectedSpace.value?.space_id
  );
});
const hasActiveTask = computed(
  () =>
    currentTask.value?.status === 'queued' ||
    currentTask.value?.status === 'running'
);
const privateKnowledgeBaseEnabled = computed(
  () => authState.session?.features.private_knowledge_base_enabled !== false
);
const canCreateSpace = computed(
  () => isAdminUser() || privateKnowledgeBaseEnabled.value
);
const canManageSelectedSpace = computed(() => {
  if (!selectedSpace.value) return false;
  if (isAdminUser()) {
    return true;
  }
  if (selectedSpace.value.visibility === 'public') {
    return isAdminUser();
  }
  return selectedSpace.value.owner_id === authState.session?.user.user_id;
});
const visibilityOptions = computed(() => {
  const options: Array<{ label: string; value: 'public' | 'private' }> = [];
  if (privateKnowledgeBaseEnabled.value) {
    options.push({ label: '私有知识库', value: 'private' });
  }
  if (isAdminUser()) {
    options.push({ label: '公有知识库', value: 'public' });
  }
  return options;
});
const summaryItems = computed(() => [
  {
    label: '知识库',
    value: `${spaceSummary.value.total_spaces} 个`,
    tone: 'neutral'
  },
  {
    label: '文档',
    value: `${stats.value.total_documents} 篇`,
    tone: 'neutral'
  },
  {
    label: '分块',
    value: `${stats.value.total_chunks} 个`,
    tone: 'success'
  }
]);

function buildApiUrl(path: string) {
  return `${getApiBase()}${path}`;
}

function buildDefaultCreateSpaceForm(
  space?: KnowledgeSpace | null
): KnowledgeSpaceCreateForm {
  return {
    name: space?.name || '',
    tags: space?.tags || '',
    description: space?.description || '',
    visibility: space?.visibility || (isAdminUser() ? 'public' : 'private')
  };
}

function buildTagList(value: string) {
  return String(value || '')
    .split(/[，,、]/)
    .map((item) => item.trim())
    .filter(Boolean);
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

function formatChunkCount(value: number) {
  return `${value || 0} 个分块`;
}

function formatImageCount(value: number) {
  return value > 0 ? `${value} 张附图` : '无附图';
}

function formatVisibilityLabel(value: 'public' | 'private') {
  return value === 'public' ? '公有' : '私有';
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return FilePdfOutlined;
  if (ext === 'doc' || ext === 'docx') return FileWordOutlined;
  return FileTextOutlined;
}

function showToast(message: string, type: 'success' | 'error' = 'success') {
  if (type === 'error') {
    oToast.error(message);
    return;
  }

  oToast.success(message);
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
  const availableIds = new Set(spaces.value.map((item) => item.space_id));

  if (preferredSpaceId && availableIds.has(preferredSpaceId)) {
    selectedSpaceId.value = preferredSpaceId;
    return;
  }

  if (selectedSpaceId.value && availableIds.has(selectedSpaceId.value)) {
    return;
  }

  selectedSpaceId.value = spaces.value[0]?.space_id || '';
}

async function refreshKnowledgeBase(preferredSpaceId = '') {
  loading.value = true;
  try {
    const [spacesRes, docsRes, statsRes] = await Promise.all([
      fetch(buildApiUrl('/api/knowledge-base/spaces'), {
        headers: buildPublicConfigHeaders()
      }),
      fetch(buildApiUrl('/api/knowledge-base/documents'), {
        headers: buildPublicConfigHeaders()
      }),
      fetch(buildApiUrl('/api/knowledge-base/stats'), {
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
      total_documents: Number(
        spacesData.summary?.total_documents || statsData.total_documents || 0
      ),
      ungrouped_documents: Number(spacesData.summary?.ungrouped_documents || 0)
    };
    syncSelectedSpace(preferredSpaceId);
  } catch {
    showToast('加载知识库失败，请检查后端服务是否正常运行', 'error');
  } finally {
    loading.value = false;
  }
}

function validateSpaceForm(payload: KnowledgeSpaceCreateForm) {
  if (!payload.name.trim()) {
    showToast('请先填写知识库名称', 'error');
    return false;
  }

  if (!payload.visibility) {
    showToast('请先选择知识库可见性', 'error');
    return false;
  }

  return true;
}

function openCreateSpaceModal() {
  if (!canCreateSpace.value) {
    showToast('当前账号不能创建知识库', 'error');
    return;
  }
  createModalMode.value = 'create';
  createSpaceForm.value = buildDefaultCreateSpaceForm();
  createModalVisible.value = true;
}

function openEditSpaceModal() {
  if (!selectedSpace.value || !canManageSelectedSpace.value) return;
  createModalMode.value = 'edit';
  createSpaceForm.value = buildDefaultCreateSpaceForm(selectedSpace.value);
  createModalVisible.value = true;
}

function closeCreateSpaceModal() {
  if (submittingSpace.value) return;
  createModalVisible.value = false;
}

function openUploadModal() {
  if (hasActiveTask.value) {
    taskProgressVisible.value = true;
    showToast('当前已有知识库任务正在执行，请先等待完成', 'error');
    return;
  }

  if (!selectedSpace.value) {
    showToast('请先选择一个知识库，再上传文档', 'error');
    return;
  }
  if (!canManageSelectedSpace.value) {
    showToast('当前账号不能向该知识库上传文档', 'error');
    return;
  }

  uploadModalVisible.value = true;
}

function closeUploadModal() {
  if (uploading.value) return;
  uploadModalVisible.value = false;
}

function resetDangerConfirm() {
  dangerConfirm.value = {
    visible: false,
    action: null,
    targetId: '',
    title: '',
    message: '',
    confirmText: '',
    impactStats: [],
    impactItems: []
  };
}

function closeDangerConfirm() {
  if (deletingSpace.value || deletingDocumentId.value) return;
  resetDangerConfirm();
}

function buildSpaceDeleteImpactStats(
  space: KnowledgeSpace
): DangerImpactStat[] {
  const relatedDocuments = documents.value.filter(
    (doc) => doc.space_id === space.space_id
  );
  const chunkCount = relatedDocuments.reduce(
    (sum, item) => sum + Number(item.chunk_count || 0),
    0
  );
  const imageCount = relatedDocuments.reduce(
    (sum, item) => sum + Number(item.image_count || 0),
    0
  );

  return [
    {
      label: '关联文档',
      value: `${relatedDocuments.length} 篇`,
      kind: 'metric'
    },
    {
      label: '文档分块',
      value: `${chunkCount} 个`,
      kind: 'metric'
    },
    {
      label: '附图资源',
      value: `${imageCount} 张`,
      kind: 'metric'
    }
  ];
}

function buildDocumentDeleteImpactStats(doc: DocumentInfo): DangerImpactStat[] {
  return [
    {
      label: '所属知识库',
      value: doc.knowledge_space || '未设置',
      kind: 'context'
    },
    {
      label: '文档分块',
      value: `${Number(doc.chunk_count || 0)} 个`,
      kind: 'metric'
    },
    {
      label: '附图资源',
      value: `${Number(doc.image_count || 0)} 张`,
      kind: 'metric'
    }
  ];
}

function openDeleteSpaceConfirm() {
  const space = selectedSpace.value;
  if (!space || deletingSpace.value || hasActiveTask.value) return;
  if (!canManageSelectedSpace.value) return;

  dangerConfirm.value = {
    visible: true,
    action: 'delete-space',
    targetId: space.space_id,
    title: `删除知识库“${space.name}”`,
    message:
      '该操作不可恢复，知识库下的全部文档、分块索引和附图资源都会被清理。',
    confirmText: '确认删除知识库',
    impactStats: buildSpaceDeleteImpactStats(space),
    impactItems: [
      '知识库记录',
      '知识库下全部文档',
      '向量索引与文本分块',
      '附图与资源目录'
    ]
  };
}

function openDeleteDocumentConfirm(doc: DocumentInfo) {
  if (!doc.doc_id || deletingDocumentId.value) return;

  dangerConfirm.value = {
    visible: true,
    action: 'delete-document',
    targetId: doc.doc_id,
    title: `删除文档“${doc.filename}”`,
    message:
      '删除后该文档会从当前知识库中彻底移除，相关分块与附图资源会同步清理。',
    confirmText: '确认删除文档',
    impactStats: buildDocumentDeleteImpactStats(doc),
    impactItems: ['当前文档记录', '文档分块', '向量索引数据', '附图与资源文件']
  };
}

async function submitSpaceForm(payload: KnowledgeSpaceCreateForm) {
  if (submittingSpace.value || !validateSpaceForm(payload)) return;

  const isEdit = createModalMode.value === 'edit' && !!selectedSpace.value;
  submittingSpace.value = true;
  try {
    const response = await fetch(
      buildApiUrl(
        isEdit
          ? `/api/knowledge-base/spaces/${encodeURIComponent(selectedSpace.value!.space_id)}`
          : '/api/knowledge-base/spaces'
      ),
      {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...buildPublicConfigHeaders()
        },
        body: JSON.stringify({
          name: payload.name.trim(),
          tags: payload.tags.trim(),
          description: payload.description.trim(),
          visibility: payload.visibility
        })
      }
    );

    const data = (await parseApiResponse(
      response
    )) as KnowledgeSpaceMutationResponsePayload;
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    const resultSpaceId =
      data.space?.space_id || selectedSpace.value?.space_id || '';
    await refreshKnowledgeBase(resultSpaceId);
    createModalVisible.value = false;
    createSpaceForm.value = buildDefaultCreateSpaceForm();
    showToast(data.message || (isEdit ? '知识库已更新' : '知识库创建成功'));
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(
      `${createModalMode.value === 'edit' ? '更新' : '创建'}知识库失败：${errMsg}`,
      'error'
    );
  } finally {
    submittingSpace.value = false;
  }
}

async function deleteSelectedSpace() {
  const targetSpace = selectedSpace.value;
  if (!targetSpace || deletingSpace.value || hasActiveTask.value) return;

  deletingSpace.value = true;
  try {
    let response = await fetch(
      buildApiUrl(
        `/api/knowledge-base/spaces/${encodeURIComponent(targetSpace.space_id)}`
      ),
      {
        method: 'DELETE',
        headers: buildPublicConfigHeaders()
      }
    );

    if (response.status === 404 || response.status === 405) {
      response = await fetch(
        buildApiUrl(
          `/api/knowledge-base/spaces/${encodeURIComponent(targetSpace.space_id)}/delete`
        ),
        {
          method: 'POST',
          headers: buildPublicConfigHeaders()
        }
      );
    }

    const data = (await parseApiResponse(response)) as {
      detail?: string;
      message?: string;
    };
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    await refreshKnowledgeBase('');
    resetDangerConfirm();
    showToast(data.message || `知识库“${targetSpace.name}”已删除`);
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除知识库失败：${errMsg}`, 'error');
  } finally {
    deletingSpace.value = false;
  }
}

function closeTaskProgressModal() {
  if (hasActiveTask.value) return;
  taskProgressVisible.value = false;
  persistTaskSnapshot(null);
  currentTask.value = null;
}

async function fetchKnowledgeBaseJob(jobId: string) {
  const response = await fetch(
    buildApiUrl(`/api/knowledge-base/jobs/${jobId}`),
    {
      headers: buildPublicConfigHeaders()
    }
  );
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

      const resultSpaceId = String(
        job.result?.space_id || selectedSpaceId.value || ''
      );
      await refreshKnowledgeBase(resultSpaceId);
      uploadModalVisible.value = false;

      if (job.status === 'completed') {
        uploadForm.value = { tags: '' };
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

    const response = await fetch(
      buildApiUrl('/api/knowledge-base/upload-jobs'),
      {
        method: 'POST',
        headers: buildPublicConfigHeaders(),
        body: formData
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

async function deleteDocument(doc: DocumentInfo) {
  if (!doc.doc_id || deletingDocumentId.value) return;

  deletingDocumentId.value = doc.doc_id;
  try {
    const response = await fetch(
      buildApiUrl(
        `/api/knowledge-base/documents/${encodeURIComponent(doc.doc_id)}`
      ),
      {
        method: 'DELETE',
        headers: buildPublicConfigHeaders()
      }
    );
    const data = (await parseApiResponse(response)) as {
      detail?: string;
      message?: string;
    };
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, response.status));
    }

    await refreshKnowledgeBase(selectedSpaceId.value);
    resetDangerConfirm();
    showToast(data.message || `文档“${doc.filename}”已删除`);
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除文档失败：${errMsg}`, 'error');
  } finally {
    deletingDocumentId.value = '';
  }
}

async function handleDangerConfirm() {
  if (dangerConfirm.value.action === 'delete-space') {
    await deleteSelectedSpace();
    return;
  }

  if (dangerConfirm.value.action === 'delete-document') {
    const doc = documents.value.find(
      (item) => item.doc_id === dangerConfirm.value.targetId
    );
    if (doc) {
      await deleteDocument(doc);
    }
  }
}

function selectSpace(spaceId: string) {
  selectedSpaceId.value = spaceId;
}

onMounted(async () => {
  await refreshKnowledgeBase();
  await restorePersistedKnowledgeBaseTask();
});

onBeforeUnmount(() => {
  clearTaskPollingTimer();
});
</script>

<template>
  <div class="o-page-stack">
    <section
      class="overflow-hidden rounded-xl border border-border bg-white px-6 py-5 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="max-w-2xl space-y-2">
          <div
            class="inline-flex items-center gap-2 rounded-full border border-border-soft bg-surface-muted px-3 py-1 text-xs font-medium text-text-secondary">
            <DatabaseOutlined />
            知识库
          </div>
          <h1 class="text-2xl font-bold tracking-tight text-heading">
            知识库管理
          </h1>
          <p class="max-w-xl text-sm text-text-secondary">
            创建知识库并上传文档以构建问答检索源。
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <OButton
            variant="ghost"
            :disabled="loading"
            @click="refreshKnowledgeBase(selectedSpaceId)">
            <ReloadOutlined :class="loading ? 'spin' : ''" />
            刷新
          </OButton>
          <OButton
            variant="secondary"
            :disabled="!canCreateSpace"
            @click="openCreateSpaceModal">
            <PlusOutlined />
            新建知识库
          </OButton>
          <OButton
            variant="primary"
            :disabled="!selectedSpace || !canManageSelectedSpace"
            @click="openUploadModal">
            <UploadOutlined />
            上传文档
          </OButton>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap gap-3">
        <OCard
          v-for="item in summaryItems"
          :key="item.label"
          padding="sm"
          class="min-w-30 bg-white/88 backdrop-blur-sm">
          <div class="text-xs text-(--oui-color-text-muted)">
            {{ item.label }}
          </div>
          <div class="mt-1 text-lg font-semibold text-(--oui-color-heading)">
            {{ item.value }}
          </div>
        </OCard>
      </div>
    </section>

    <div class="grid grid-cols-[300px_minmax(0,1fr)] gap-4 max-lg:grid-cols-1">
      <OCard padding="sm" class="min-h-128 flex flex-col gap-2">
        <div
          class="flex items-center justify-between gap-3 border-b border-(--oui-color-border)/80 px-1 pb-2.5">
          <div>
            <div class="text-sm font-semibold text-(--oui-color-heading)">
              知识库列表
            </div>
            <div class="text-xs leading-5 text-(--oui-color-text-muted)">
              您的知识库集合。
            </div>
          </div>
          <OBadge tone="neutral">{{ spaces.length }}</OBadge>
        </div>

        <div
          v-if="loading"
          class="flex min-h-105 items-center justify-center text-sm text-(--oui-color-text-muted)">
          <LoadingOutlined class="mr-2 spin" />
          正在同步知识库...
        </div>

        <div v-else-if="spaces.length > 0" class="mt-3 space-y-3">
          <button
            v-for="space in spaces"
            :key="space.space_id"
            type="button"
            :class="[
              'w-full rounded-xl border px-3.5 py-3 text-left transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-blue-500/20',
              selectedSpaceId === space.space_id
                ? 'border-zinc-900 ring-1 ring-zinc-900 bg-zinc-50 shadow-sm'
                : 'border-border bg-white hover:border-border-strong hover:bg-surface-soft'
            ]"
            @click="selectSpace(space.space_id)">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div
                  class="truncate text-sm font-semibold text-(--oui-color-heading)">
                  {{ space.name }}
                </div>
                <div
                  class="mt-1 text-xs leading-5 text-(--oui-color-text-muted)">
                  {{ space.description || '暂无说明' }}
                </div>
              </div>
              <div class="flex flex-col items-end gap-1">
                <OBadge tone="neutral">{{ space.document_count || 0 }}</OBadge>
                <span class="text-[11px] font-semibold text-text-muted">
                  {{ formatVisibilityLabel(space.visibility) }}
                </span>
              </div>
            </div>

            <div
              v-if="buildTagList(space.tags).length > 0"
              class="mt-2.5 flex flex-wrap gap-1.5">
              <span
                v-for="tag in buildTagList(space.tags)"
                :key="tag"
                class="rounded-full bg-surface-muted px-2.5 py-1 text-[11px] font-medium text-text-secondary border border-border-soft">
                {{ tag }}
              </span>
            </div>
          </button>
        </div>

        <div v-else class="py-10">
          <OEmptyState
            title="暂无知识库"
            description="点击右上角新建以开始。" />
        </div>
      </OCard>

      <div class="space-y-3 flex flex-col gap-4">
        <OCard
          v-if="selectedSpace"
          padding="none"
          class="px-4 py-3.5 sm:px-5 sm:py-4">
          <div
            class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start sm:gap-4">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <div class="text-xl font-semibold text-(--oui-color-heading)">
                  {{ selectedSpace.name }}
                </div>
                <OBadge tone="neutral">
                  {{ visibleDocuments.length }} 篇文档
                </OBadge>
                <OBadge
                  :tone="
                    selectedSpace.visibility === 'public'
                      ? 'warning'
                      : 'neutral'
                  ">
                  {{ formatVisibilityLabel(selectedSpace.visibility) }}
                </OBadge>
              </div>
              <div
                class="max-w-2xl text-sm leading-5.5 text-(--oui-color-text-secondary)">
                {{ selectedSpace.description || '暂无说明。' }}
              </div>
              <div
                class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-(--oui-color-text-muted)">
                <span>创建于 {{ formatDate(selectedSpace.created_at) }}</span>
                <span v-if="selectedSpace.updated_at">
                  最近更新 {{ formatDate(selectedSpace.updated_at) }}
                </span>
              </div>
              <div
                v-if="buildTagList(selectedSpace.tags).length > 0"
                class="flex flex-wrap gap-1.5 pt-0.5">
                <span
                  v-for="tag in buildTagList(selectedSpace.tags)"
                  :key="tag"
                  class="rounded-full bg-(--oui-color-primary-soft) px-2.5 py-1 text-[11px] font-medium text-(--oui-color-primary)">
                  {{ tag }}
                </span>
              </div>
            </div>

            <div class="flex flex-wrap gap-2 sm:justify-end sm:self-start">
              <OButton
                variant="ghost"
                :disabled="!canManageSelectedSpace"
                @click="openEditSpaceModal">
                <EditOutlined />
                编辑
              </OButton>
              <OButton
                variant="ghost"
                :disabled="!canManageSelectedSpace"
                @click="openUploadModal">
                <UploadOutlined />
                上传文档
              </OButton>
              <OButton
                variant="danger"
                :disabled="!canManageSelectedSpace"
                @click="openDeleteSpaceConfirm">
                <DeleteOutlined />
                删除知识库
              </OButton>
            </div>
          </div>
        </OCard>

        <OCard
          padding="none"
          class="px-4 py-3.5 sm:px-5 sm:py-4 flex flex-col gap-2">
          <div
            class="flex items-center justify-between gap-3 border-b border-(--oui-color-border)/80 px-1 pb-2.5">
            <div>
              <div class="text-sm font-semibold text-(--oui-color-heading)">
                文档列表
              </div>
              <div class="text-xs leading-5 text-(--oui-color-text-muted)">
                {{
                  selectedSpace
                    ? '当前知识库的文档与索引。'
                    : '请先选择要查看的知识库。'
                }}
              </div>
            </div>
            <OBadge tone="neutral">{{ visibleDocuments.length }}</OBadge>
          </div>

          <div v-if="!selectedSpace" class="py-12">
            <OEmptyState
              title="请选择知识库"
              description="请在左侧选择要查看的知识库。" />
          </div>

          <div v-else-if="visibleDocuments.length === 0" class="py-12">
            <OEmptyState
              title="当前知识库还没有文档"
              description="上传文档后，系统将自动构建索引。" />
          </div>

          <div v-else class="mt-3 space-y-3">
            <OPanelRow
              v-for="doc in visibleDocuments"
              :key="doc.doc_id"
              class="items-start gap-3 rounded-[18px] border border-(--oui-color-border) px-3.5 py-3.5">
              <div class="flex min-w-0 flex-1 items-start gap-2.5">
                <component
                  :is="getFileIcon(doc.filename)"
                  class="mt-0.5 text-lg text-(--oui-color-primary)" />
                <div class="min-w-0 flex-1 space-y-1.5">
                  <div>
                    <div
                      class="truncate text-sm font-semibold text-(--oui-color-heading)">
                      {{ doc.filename }}
                    </div>
                    <div
                      class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-(--oui-color-text-muted)">
                      <span>{{ formatDate(doc.upload_time) }}</span>
                      <span>{{ formatChunkCount(doc.chunk_count) }}</span>
                      <span>{{ formatImageCount(doc.image_count) }}</span>
                    </div>
                  </div>

                  <div
                    v-if="buildTagList(doc.tags).length > 0"
                    class="flex flex-wrap gap-1.5">
                    <span
                      v-for="tag in buildTagList(doc.tags)"
                      :key="`${doc.doc_id}-${tag}`"
                      class="rounded-full bg-(--oui-color-surface-soft) px-2.5 py-1 text-[11px] font-medium text-(--oui-color-text-secondary)">
                      {{ tag }}
                    </span>
                  </div>
                </div>
              </div>

              <OButton
                variant="ghost"
                :disabled="
                  deletingDocumentId === doc.doc_id || !canManageSelectedSpace
                "
                @click="openDeleteDocumentConfirm(doc)">
                <DeleteOutlined />
                删除
              </OButton>
            </OPanelRow>
          </div>
        </OCard>
      </div>
    </div>

    <KnowledgeSpaceCreateModal
      :visible="createModalVisible"
      :submitting="submittingSpace"
      :mode="createModalMode"
      :initial-form="createSpaceForm"
      :visibility-options="visibilityOptions"
      :visibility-disabled="createModalMode === 'edit'"
      @close="closeCreateSpaceModal"
      @submit="submitSpaceForm" />

    <KnowledgeUploadModal
      :visible="uploadModalVisible"
      :submitting="uploading"
      :selected-space="selectedSpace"
      :initial-form="uploadForm"
      @close="closeUploadModal"
      @submit="handleUploadSubmit" />

    <KnowledgeDangerConfirmModal
      :visible="dangerConfirm.visible"
      :title="dangerConfirm.title"
      :message="dangerConfirm.message"
      :confirm-text="dangerConfirm.confirmText"
      :impact-stats="dangerConfirm.impactStats"
      :impact-items="dangerConfirm.impactItems"
      :submitting="deletingSpace || !!deletingDocumentId"
      @close="closeDangerConfirm"
      @confirm="handleDangerConfirm" />

    <KnowledgeBaseTaskProgressModal
      :visible="taskProgressVisible"
      :task="currentTask"
      @close="closeTaskProgressModal" />
  </div>
</template>
