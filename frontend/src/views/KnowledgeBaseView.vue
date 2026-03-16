<script setup lang="ts">
defineOptions({
  name: 'KnowledgeBaseView'
});

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  CaretDownOutlined,
  CaretRightOutlined,
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
import KnowledgeDangerConfirmModal from '@/components/knowledge-base/KnowledgeDangerConfirmModal.vue';
import KnowledgeBaseTaskProgressModal from '@/components/knowledge-base/KnowledgeBaseTaskProgressModal.vue';
import KnowledgeUploadModal from '@/components/knowledge-base/KnowledgeUploadModal.vue';
import UngroupedMigrationModal from '@/components/knowledge-base/UngroupedMigrationModal.vue';
import { OButton, OCard, OTree, useOToast } from '@/orange-ui';
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

type DangerActionType = 'delete-space' | 'delete-document';

interface DangerImpactStat {
  label: string;
  value: string;
}

interface DangerConfirmState {
  visible: boolean;
  action: DangerActionType | null;
  targetId: string;
  targetLabel: string;
  title: string;
  message: string;
  confirmText: string;
  impactStats: DangerImpactStat[];
  impactItems: string[];
}

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
const deletingSpace = ref(false);
const deletingDocumentId = ref('');
const uploading = ref(false);
const migratingUngrouped = ref(false);
const createModalVisible = ref(false);
const uploadModalVisible = ref(false);
const migrationModalVisible = ref(false);
const taskProgressVisible = ref(false);
const currentTask = ref<KnowledgeBaseJobStatus | null>(null);
const dangerConfirm = ref<DangerConfirmState>({
  visible: false,
  action: null,
  targetId: '',
  targetLabel: '',
  title: '',
  message: '',
  confirmText: '',
  impactStats: [],
  impactItems: []
});
const expandedSpaceIds = ref<string[]>([]);
const oToast = useOToast();
let taskPollingTimer: number | null = null;

const createSpaceForm = ref<KnowledgeSpaceCreateForm>({
  name: '',
  parent_id: '',
  category: '',
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
const spaceMap = computed(
  () => new Map(flatSpaces.value.map((item) => [item.space_id, item]))
);
const selectedSpace = computed(
  () =>
    flatSpaces.value.find((item) => item.space_id === selectedSpaceId.value) ||
    null
);
const visibleTreeSpaces = computed(() => {
  const items: KnowledgeSpace[] = [];

  const walk = (nodes: KnowledgeSpace[]) => {
    for (const node of nodes) {
      items.push(node);
      if (
        Array.isArray(node.children) &&
        node.children.length > 0 &&
        expandedSpaceIds.value.includes(node.space_id)
      ) {
        walk(node.children);
      }
    }
  };

  walk(spaces.value);
  return items;
});
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
    category: '',
    topic: '',
    tags: '',
    version_label: '',
    description: ''
  };
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

function hasChildSpaces(space: KnowledgeSpace) {
  return Array.isArray(space.children) && space.children.length > 0;
}

function isSpaceExpanded(spaceId: string) {
  return expandedSpaceIds.value.includes(spaceId);
}

function ensureExpanded(spaceId: string) {
  if (!expandedSpaceIds.value.includes(spaceId)) {
    expandedSpaceIds.value = [...expandedSpaceIds.value, spaceId];
  }
}

function expandAncestors(spaceId: string) {
  let current = spaceMap.value.get(spaceId);
  while (current?.parent_id) {
    ensureExpanded(current.parent_id);
    current = spaceMap.value.get(current.parent_id);
  }
}

function toggleSpaceExpanded(spaceId: string) {
  if (expandedSpaceIds.value.includes(spaceId)) {
    expandedSpaceIds.value = expandedSpaceIds.value.filter(
      (item) => item !== spaceId
    );
    return;
  }

  ensureExpanded(spaceId);
}

function collectDescendantSpaceIds(spaceId: string) {
  const descendantIds = new Set<string>();
  const queue = [spaceId];

  while (queue.length > 0) {
    const currentId = queue.shift();
    if (!currentId || descendantIds.has(currentId)) continue;

    descendantIds.add(currentId);
    flatSpaces.value
      .filter((item) => item.parent_id === currentId)
      .forEach((item) => {
        queue.push(item.space_id);
      });
  }

  return descendantIds;
}

function buildSpaceDeleteImpactStats(
  space: KnowledgeSpace
): DangerImpactStat[] {
  const relatedSpaceIds = collectDescendantSpaceIds(space.space_id);
  const relatedDocuments = documents.value.filter((doc) =>
    relatedSpaceIds.has(String(doc.space_id || '').trim())
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
      label: '覆盖空间',
      value: `${relatedSpaceIds.size} 个`
    },
    {
      label: '关联文档',
      value: `${relatedDocuments.length} 篇`
    },
    {
      label: '文档分块',
      value: `${chunkCount} 个`
    },
    {
      label: '附图资源',
      value: `${imageCount} 张`
    }
  ];
}

function buildDocumentDeleteImpactStats(doc: DocumentInfo): DangerImpactStat[] {
  return [
    {
      label: '所属空间',
      value: formatMetadata(doc.knowledge_space)
    },
    {
      label: '文档分块',
      value: `${Number(doc.chunk_count || 0)} 个`
    },
    {
      label: '附图资源',
      value: `${Number(doc.image_count || 0)} 张`
    }
  ];
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

function normalizeCreateSpaceErrorMessage(message: string) {
  const normalized = String(message || '').trim();
  if (normalized === '主题不能为空' || normalized === '分类不能为空') {
    return '当前后端仍在使用旧的必填校验，请重启后端后重试。';
  }

  return normalized;
}

function syncSelectedSpace(preferredSpaceId = '') {
  const availableIds = new Set(flatSpaces.value.map((item) => item.space_id));

  if (preferredSpaceId && availableIds.has(preferredSpaceId)) {
    selectedSpaceId.value = preferredSpaceId;
    expandAncestors(preferredSpaceId);
    return;
  }

  if (selectedSpaceId.value && availableIds.has(selectedSpaceId.value)) {
    expandAncestors(selectedSpaceId.value);
    return;
  }

  selectedSpaceId.value = flatSpaces.value[0]?.space_id || '';
  if (selectedSpaceId.value) {
    ensureExpanded(selectedSpaceId.value);
  }
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

function resetDangerConfirm() {
  dangerConfirm.value = {
    visible: false,
    action: null,
    targetId: '',
    targetLabel: '',
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

function openDeleteSpaceConfirm() {
  const space = selectedSpace.value;
  if (!space || deletingSpace.value || hasActiveTask.value) return;

  dangerConfirm.value = {
    visible: true,
    action: 'delete-space',
    targetId: space.space_id,
    targetLabel: space.path,
    title: `删除空间“${space.name}”`,
    message: '该操作不可恢复。确认后会递归清理当前空间下的全部结构和索引数据。',
    confirmText: '确认删除空间',
    impactStats: buildSpaceDeleteImpactStats(space),
    impactItems: [
      '当前知识空间',
      '所有子空间',
      '空间下全部文档',
      '文档分块与向量索引',
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
    targetLabel: doc.filename,
    title: `删除文档“${doc.filename}”`,
    message:
      '删除后该文档将从知识库中彻底移除，相关分块和附图资源也会同步清理。',
    confirmText: '确认删除文档',
    impactStats: buildDocumentDeleteImpactStats(doc),
    impactItems: [
      '当前文档记录',
      '文档文本分块',
      '向量索引数据',
      '附图与资源文件'
    ]
  };
}

async function deleteSelectedSpace() {
  const targetSpaceId = String(dangerConfirm.value.targetId || '').trim();
  const targetSpace =
    spaceMap.value.get(targetSpaceId) ||
    (selectedSpace.value?.space_id === targetSpaceId
      ? selectedSpace.value
      : null);
  if (!targetSpaceId || deletingSpace.value || hasActiveTask.value) return;

  deletingSpace.value = true;
  try {
    const fallbackParentId = String(targetSpace?.parent_id || '').trim();
    let response = await fetch(
      `${API_BASE}/api/knowledge-base/spaces/${encodeURIComponent(targetSpaceId)}`,
      {
        method: 'DELETE',
        headers: buildPublicConfigHeaders()
      }
    );
    if (response.status === 404 || response.status === 405) {
      response = await fetch(
        `${API_BASE}/api/knowledge-base/spaces/${encodeURIComponent(targetSpaceId)}/delete`,
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

    selectedSpaceId.value = fallbackParentId;
    await refreshKnowledgeBase(fallbackParentId);
    resetDangerConfirm();
    showToast(
      data.message ||
        `知识空间“${targetSpace?.path || dangerConfirm.value.targetLabel || targetSpaceId}”已删除`
    );
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除知识空间失败：${errMsg}`, 'error');
  } finally {
    deletingSpace.value = false;
  }
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
    const errMsg = normalizeCreateSpaceErrorMessage(
      err instanceof Error ? err.message : String(err)
    );
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
  deletingDocumentId.value = doc.doc_id;
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
    await refreshKnowledgeBase(selectedSpace.value?.space_id || '');
    resetDangerConfirm();
    showToast(`已删除文档“${doc.filename}”`);
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err);
    showToast(`删除失败：${errMsg}`, 'error');
  } finally {
    deletingDocumentId.value = '';
  }
}

async function confirmDangerAction() {
  if (!dangerConfirm.value.action) return;

  if (dangerConfirm.value.action === 'delete-space') {
    await deleteSelectedSpace();
    return;
  }

  if (dangerConfirm.value.action === 'delete-document') {
    const doc = visibleDocuments.value.find(
      (item) => item.doc_id === dangerConfirm.value.targetId
    );
    if (!doc) {
      closeDangerConfirm();
      showToast('目标文档不存在或已被移除', 'error');
      return;
    }

    await deleteDocument(doc);
  }
}

function selectSpace(spaceId: string) {
  selectedSpaceId.value = spaceId;
  expandAncestors(spaceId);
}

function assignSelectedSpaceAsParent() {
  openCreateSpaceModal(selectedSpace.value?.space_id || '');
}

function getSpaceTreeCount(
  space:
    | { direct_document_count: number; total_document_count: number }
    | Record<string, any>
) {
  return `${space.direct_document_count}/${space.total_document_count}`;
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
  <div class="mx-auto flex w-full max-w-full flex-col gap-4 pb-4.5">
    <section
      class="flex items-center justify-between gap-6 px-1 pt-3 pb-1 max-[720px]:flex-col max-[720px]:items-stretch">
      <div class="m-0 flex-none">
        <div>
          <h1
            class="m-0 text-[20px] leading-[1.05] font-bold tracking-tight text-zinc-900 max-[720px]:text-[22px]">
            知识空间
          </h1>
        </div>
      </div>

      <div class="grid grid-cols-4 gap-3 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <OCard
          v-for="item in summaryItems"
          :key="item.label"
          :tone="
            item.tone === 'success'
              ? 'success'
              : item.tone === 'warning'
                ? 'warning'
                : 'default'
          "
          padding="sm"
          :html-class="'min-h-28'">
          <div class="text-xs text-zinc-500">{{ item.label }}</div>
          <div class="mt-0 text-base font-bold text-zinc-900">
            {{ item.value }}
          </div>
        </OCard>
      </div>
    </section>

    <section
      class="grid grid-cols-[minmax(360px,430px)_minmax(0,1fr)] items-start gap-5 max-[1024px]:grid-cols-1">
      <OCard padding="lg" html-class="min-w-0 sticky top-0 max-[1024px]:static">
        <div
          class="flex items-start justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
          <div class="min-w-0 flex-1">
            <div class="text-base font-bold text-zinc-900">空间树</div>
            <div class="mt-1.5 text-xs leading-6 text-zinc-500">
              {{ flatSpaces.length }} 个正式空间 ·
              {{ spaceSummary.ungrouped_documents }} 篇待归类文档
            </div>
          </div>
          <OButton
            v-if="selectedSpace"
            variant="secondary"
            size="sm"
            html-class="rounded-full"
            :disabled="hasActiveTask"
            @click="assignSelectedSpaceAsParent">
            <PlusOutlined />
            子空间
          </OButton>
        </div>

        <div
          class="mt-3 flex max-h-[min(72vh,820px)] flex-col gap-3 overflow-auto rounded-[22px] border border-black/5 bg-linear-to-b from-[rgba(24,24,27,0.015)] to-[rgba(24,24,27,0.04)] p-3.5 shadow-inner">
          <div
            class="grid min-h-18 grid-cols-[auto_minmax(0,1fr)] items-stretch gap-2.5 pl-0">
            <span
              class="pointer-events-none invisible inline-flex min-h-full w-8 items-center justify-center rounded-xl bg-black/4 text-zinc-500" />
            <button
              type="button"
              :class="[
                'relative flex min-h-18 w-full items-center justify-between gap-3.5 rounded-[22px] border px-4.5 py-4 pr-4.5 pl-5 text-left transition',
                !selectedSpaceId
                  ? 'border-transparent bg-linear-to-br from-zinc-900 to-zinc-800 shadow-[0_20px_34px_rgba(24,24,27,0.18)]'
                  : 'border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] hover:border-black/14 hover:shadow-[0_10px_20px_rgba(24,24,27,0.05)]'
              ]"
              @click="selectedSpaceId = ''">
              <span
                :class="[
                  'absolute top-3 bottom-3 left-2.5 w-1 rounded-full opacity-70',
                  !selectedSpaceId ? 'bg-white/35' : 'bg-black/8'
                ]" />
              <div class="flex min-w-0 items-center gap-3.5">
                <FolderOpenOutlined
                  :class="
                    !selectedSpaceId
                      ? 'text-lg text-white'
                      : 'text-lg text-zinc-500'
                  " />
                <div class="grid min-w-0 gap-1">
                  <div
                    :class="
                      !selectedSpaceId
                        ? 'text-sm leading-[1.4] font-bold text-white'
                        : 'text-sm leading-[1.4] font-bold text-zinc-900'
                    ">
                    未归类文档
                  </div>
                  <div
                    :class="
                      !selectedSpaceId
                        ? 'text-xs wrap-break-word text-white'
                        : 'text-xs wrap-break-word text-(--color-text-muted)'
                    ">
                    旧数据过渡区，不建议继续上传
                  </div>
                </div>
              </div>
              <span
                :class="[
                  'min-w-15 shrink-0 rounded-full border px-3 py-2 text-center text-xs font-bold',
                  !selectedSpaceId
                    ? 'border-transparent bg-white/12 text-white'
                    : 'border-black/8 bg-zinc-100 text-zinc-600'
                ]">
                {{ spaceSummary.ungrouped_documents }}
              </span>
            </button>
          </div>

          <div
            v-if="flatSpaces.length === 0"
            class="mt-1 flex min-h-60 flex-col items-center justify-center rounded-[22px] border border-dashed border-black/12 bg-white/70 px-4.5 py-8 text-center text-zinc-500">
            <FolderOpenOutlined class="mb-3 text-3xl text-zinc-400" />
            <p>还没有知识空间，请先创建一个顶级空间。</p>
            <OButton variant="secondary" @click="openCreateSpaceModal()">
              <PlusOutlined />
              创建第一个空间
            </OButton>
          </div>

          <OTree
            v-if="flatSpaces.length > 0"
            :items="visibleTreeSpaces"
            :selected-key="selectedSpaceId"
            :expanded-keys="expandedSpaceIds"
            :get-key="(space) => space.space_id"
            :get-label="(space) => space.name"
            :get-description="(space) => space.path"
            :get-count="(space) => getSpaceTreeCount(space)"
            :get-children="(space) => space.children || []"
            :get-depth="(space) => space.depth"
            @select="selectSpace($event.space_id)"
            @toggle="toggleSpaceExpanded($event.space_id)" />
        </div>
      </OCard>

      <div class="grid min-w-0 gap-4.5">
        <OCard v-if="selectedSpace" padding="lg" html-class="kb-focus-panel">
          <div
            class="mb-4.5 flex items-start justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
            <div class="min-w-0 flex-1">
              <div class="text-base font-bold text-zinc-900">
                {{ selectedSpace ? selectedSpace.name : '未归类文档' }}
              </div>
              <div class="text-[13px] leading-[1.7] text-(--color-text-muted)">
                {{ selectedSpace ? selectedSpace.path : '历史遗留数据过渡区' }}
              </div>
            </div>
            <div
              class="flex flex-wrap items-start justify-end gap-3 max-[720px]:justify-start">
              <OButton
                v-if="selectedSpace"
                variant="danger"
                :disabled="hasActiveTask || deletingSpace"
                @click="openDeleteSpaceConfirm">
                <DeleteOutlined />
                {{ deletingSpace ? '删除中...' : '删除空间' }}
              </OButton>
              <OButton
                v-if="selectedSpace"
                variant="secondary"
                :disabled="hasActiveTask"
                @click="assignSelectedSpaceAsParent">
                <PlusOutlined />
                新建子空间
              </OButton>
              <OButton
                :disabled="!selectedSpace || hasActiveTask"
                @click="openUploadModal">
                <UploadOutlined />
                上传到当前空间
              </OButton>
            </div>
          </div>

          <div
            class="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3 max-lg:grid-cols-2 max-sm:grid-cols-1">
            <div
              class="rounded-[18px] border border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] p-3.5">
              <span class="text-xs text-zinc-500">直属文档</span>
              <strong class="mt-1.5 block text-xl font-bold text-zinc-900">
                {{ selectedSpace.direct_document_count }}
              </strong>
            </div>
            <div
              class="rounded-[18px] border border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] p-3.5">
              <span class="text-xs text-zinc-500">全部文档</span>
              <strong class="mt-1.5 block text-xl font-bold text-zinc-900">
                {{ selectedSpace.total_document_count }}
              </strong>
            </div>
            <div
              class="rounded-[18px] border border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] p-3.5">
              <span class="text-xs text-zinc-500">子空间</span>
              <strong class="mt-1.5 block text-xl font-bold text-zinc-900">
                {{ selectedSpace.child_count }}
              </strong>
            </div>
            <div
              class="rounded-[18px] border border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] p-3.5">
              <span class="text-xs text-zinc-500">创建时间</span>
              <strong
                class="mt-1.5 block text-sm leading-6 font-bold text-zinc-900">
                {{ formatDate(selectedSpace.created_at) }}
              </strong>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <span
              class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
              分类 · {{ formatMetadata(selectedSpace.category) }}
            </span>
            <span
              class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
              主题 · {{ formatMetadata(selectedSpace.topic) }}
            </span>
            <span
              v-if="selectedSpace.version_label"
              class="inline-flex min-h-7.5 items-center rounded-full bg-[rgba(37,99,65,0.12)] px-2.5 py-1 text-xs font-semibold text-[#1f6b42]">
              版本 · {{ selectedSpace.version_label }}
            </span>
            <span
              v-for="tag in formatTagList(selectedSpace.tags)"
              :key="`${selectedSpace.space_id}-${tag}`"
              class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
              {{ tag }}
            </span>
          </div>

          <p class="mt-4 text-[13px] leading-[1.7] text-(--color-text-muted)">
            {{ selectedSpace.description || '当前空间未填写额外说明。' }}
          </p>

          <div v-if="childSpaces.length > 0" class="mt-5">
            <div class="text-[13px] font-bold text-(--color-text-secondary)">
              下一级空间
            </div>
            <div
              class="mt-2.5 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
              <button
                v-for="space in childSpaces"
                :key="space.space_id"
                type="button"
                class="rounded-[18px] border border-black/8 bg-linear-to-b from-[#fcfcfd] to-[#f5f5f5] p-4 text-left transition duration-200 hover:-translate-y-0.5 hover:border-black/14 hover:shadow-[0_12px_24px_rgba(24,24,27,0.06)]"
                @click="selectSpace(space.space_id)">
                <div class="font-bold text-zinc-900">{{ space.name }}</div>
                <div
                  class="mt-1.5 text-[13px] leading-[1.7] text-(--color-text-muted)">
                  {{ space.path }}
                </div>
                <div
                  class="mt-1.5 text-[13px] leading-[1.7] text-(--color-text-muted)">
                  {{ space.child_count }} 个子空间 ·
                  {{ space.total_document_count }} 篇文档
                </div>
              </button>
            </div>
          </div>
        </OCard>

        <OCard padding="lg" html-class="kb-docs-panel">
          <div
            class="flex items-start justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
            <div class="min-w-0 flex-1">
              <div class="text-base font-bold text-zinc-900">
                {{ documentPanelTitle }}
              </div>
              <div class="text-[13px] leading-[1.7] text-(--color-text-muted)">
                {{ documentPanelSubtitle }}
              </div>
            </div>
            <div
              class="flex flex-wrap items-center justify-end gap-2.5 max-[720px]:justify-start">
              <OButton
                variant="secondary"
                size="sm"
                :disabled="loading"
                @click="refreshKnowledgeBase(selectedSpaceId)">
                <ReloadOutlined :class="loading ? 'animate-spin' : ''" />
                刷新
              </OButton>
              <div
                class="min-w-15 shrink-0 rounded-full border border-black/8 bg-zinc-100 px-3 py-2 text-center text-xs font-bold text-zinc-900">
                {{ visibleDocuments.length }} 篇
              </div>
            </div>
          </div>

          <OCard
            v-if="!selectedSpace"
            tone="warning"
            padding="md"
            html-class="mb-4.5">
            <div>
              <div class="text-base font-bold text-zinc-900">
                未归类文档过渡区
              </div>
              <div
                class="mt-2 max-w-190 text-[13px] leading-[1.7] text-zinc-600">
                当前是历史遗留数据的过渡视图。建议尽快创建正式知识空间，并将这些文档迁移到目标空间以重建索引。
              </div>
            </div>
            <div
              class="mt-4 flex items-start justify-between gap-4 border-t border-[rgba(180,125,29,0.12)] pt-4 max-[720px]:flex-col">
              <div>
                <div class="text-sm font-bold text-[#9f670f]">
                  迁移时会重新 embedding
                </div>
                <div class="mt-1 text-[13px] leading-[1.6] text-zinc-500">
                  批量迁移会把目标空间的元数据重新写入这些文档，并重建对应向量索引，请尽量在低峰时段操作。
                </div>
              </div>
              <div
                class="flex flex-wrap justify-end gap-2.5 max-[720px]:w-full max-[720px]:justify-stretch">
                <OButton
                  v-if="spaceSummary.ungrouped_documents > 0"
                  variant="warning"
                  html-class="min-w-38.5"
                  :disabled="hasActiveTask"
                  @click="openMigrationModal">
                  <WarningOutlined />
                  批量迁移并重建索引
                </OButton>
                <OButton
                  variant="secondary"
                  html-class="min-w-38.5"
                  :disabled="hasActiveTask"
                  @click="openCreateSpaceModal()">
                  <PlusOutlined />
                  新建顶级空间
                </OButton>
              </div>
            </div>
          </OCard>

          <div
            v-if="loading && documents.length === 0"
            class="flex flex-col items-center justify-center rounded-[18px] border border-dashed border-black/12 bg-[rgba(250,250,250,0.5)] px-5 py-10.5 text-center text-zinc-500">
            <LoadingOutlined class="mb-3 animate-spin text-3xl text-zinc-400" />
            <p>正在加载文档列表...</p>
          </div>
          <div
            v-else-if="visibleDocuments.length === 0"
            class="flex flex-col items-center justify-center rounded-[18px] border border-dashed border-black/12 bg-[rgba(250,250,250,0.5)] px-5 py-10.5 text-center text-zinc-500">
            <DatabaseOutlined class="mb-3 text-3xl text-zinc-400" />
            <p>
              {{
                selectedSpace
                  ? '当前空间还没有直属文档，可以先上传文件，或进入子空间继续查看。'
                  : '暂无未归类文档。'
              }}
            </p>
          </div>
          <div
            v-else
            class="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-3 max-[720px]:grid-cols-1">
            <TransitionGroup
              enter-active-class="transition duration-200 ease-out"
              leave-active-class="transition duration-200 ease-out"
              enter-from-class="translate-y-3 opacity-0"
              leave-to-class="translate-y-3 opacity-0">
              <OCard
                v-for="doc in visibleDocuments"
                :key="doc.doc_id"
                padding="md"
                html-class="kb-doc-card">
                <div
                  class="flex items-center justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
                  <div class="flex min-w-0 flex-1 items-start gap-3">
                    <div
                      class="flex h-10.5 w-10.5 shrink-0 items-center justify-center rounded-[14px] bg-zinc-100">
                      <component
                        :is="getFileIcon(doc.filename)"
                        class="shrink-0 text-lg text-zinc-600" />
                    </div>
                    <h3
                      class="wrap-break-word text-sm leading-normal font-bold text-zinc-900"
                      :title="doc.filename">
                      {{ doc.filename }}
                    </h3>
                  </div>
                  <button
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-transparent text-[#9e3328] transition hover:bg-[rgba(177,55,42,0.08)] disabled:cursor-not-allowed disabled:opacity-55"
                    type="button"
                    title="删除文档"
                    @click="openDeleteDocumentConfirm(doc)">
                    <DeleteOutlined />
                  </button>
                </div>

                <div class="mt-3.5 flex flex-wrap gap-2">
                  <span
                    class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
                    {{ formatMetadata(doc.category) }}
                  </span>
                  <span
                    class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
                    {{ formatMetadata(doc.knowledge_space) }}
                  </span>
                  <span
                    v-if="doc.topic"
                    class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
                    {{ doc.topic }}
                  </span>
                  <template v-if="doc.tags">
                    <span
                      v-for="tag in formatTagList(doc.tags)"
                      :key="`${doc.doc_id}-${tag}`"
                      class="inline-flex min-h-7.5 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
                      {{ tag }}
                    </span>
                  </template>
                  <span
                    v-if="doc.version_label"
                    class="inline-flex min-h-7.5 items-center rounded-full bg-[rgba(37,99,65,0.12)] px-2.5 py-1 text-xs font-semibold text-[#1f6b42]">
                    {{ doc.version_label }}
                  </span>
                </div>

                <div
                  class="mt-4 flex flex-wrap items-center justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
                  <div class="flex items-center gap-2">
                    <span
                      class="text-[13px] leading-[1.7] text-(--color-text-muted)">
                      上传于
                    </span>
                    <span
                      class="text-[13px] leading-[1.7] text-(--color-text-muted)">
                      {{ formatDate(doc.upload_time) }}
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      class="inline-flex min-h-7 items-center rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-600">
                      {{ formatChunkCount(doc.chunk_count) }}
                    </span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      :class="[
                        'inline-flex min-h-7 items-center rounded-full px-2.5 py-1 text-xs font-semibold',
                        doc.image_count > 0
                          ? 'bg-[rgba(37,99,65,0.12)] text-[#1f6b42]'
                          : 'bg-zinc-100 text-zinc-600'
                      ]">
                      {{ formatImageCount(doc.image_count) }}
                    </span>
                  </div>
                </div>
              </OCard>
            </TransitionGroup>
          </div>
        </OCard>
      </div>
    </section>

    <KnowledgeSpaceCreateModal
      :visible="createModalVisible"
      :submitting="creatingSpace"
      :spaces="flatSpaces"
      :category-options="CATEGORY_OPTIONS"
      :initial-form="createSpaceForm"
      @close="closeCreateSpaceModal"
      @submit="createSpace" />

    <KnowledgeDangerConfirmModal
      :visible="dangerConfirm.visible"
      :title="dangerConfirm.title"
      :message="dangerConfirm.message"
      :impact-stats="dangerConfirm.impactStats"
      :impact-items="dangerConfirm.impactItems"
      :confirm-text="dangerConfirm.confirmText"
      :submitting="deletingSpace || !!deletingDocumentId"
      @close="closeDangerConfirm"
      @confirm="confirmDangerAction" />

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
