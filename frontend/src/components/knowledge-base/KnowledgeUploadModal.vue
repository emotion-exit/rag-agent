<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  CloseOutlined,
  InboxOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  UploadOutlined
} from '@ant-design/icons-vue';
import KnowledgeDangerConfirmModal from '@/components/knowledge-base/KnowledgeDangerConfirmModal.vue';
import type {
  KnowledgeSpace,
  UploadForm,
  UploadSubmitPayload
} from '@/types/knowledgeBase';

defineOptions({
  name: 'KnowledgeUploadModal'
});

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  selectedSpace: KnowledgeSpace | null;
  initialForm: UploadForm;
}>();

const emit = defineEmits<{
  close: [];
  submit: [payload: UploadSubmitPayload];
}>();

const localForm = ref<UploadForm>({ ...props.initialForm });
const selectedFiles = ref<File[]>([]);
const dragOver = ref(false);
const localWarning = ref('');
const localTagInput = ref('');
const removeConfirmVisible = ref(false);
const pendingRemoveIndex = ref(-1);

const pendingRemoveFile = computed(
  () => selectedFiles.value[pendingRemoveIndex.value] || null
);
const pendingRemoveStats = computed(() => {
  const file = pendingRemoveFile.value;
  if (!file) return [];

  return [
    {
      label: '文件大小',
      value: `${Math.max(file.size / 1024 / 1024, 0.01).toFixed(2)} MB`
    },
    {
      label: '当前队列',
      value: `${selectedFiles.value.length} 个`
    }
  ];
});

function parseTagList(value: string) {
  return Array.from(
    new Set(
      String(value || '')
        .split(/[，,、\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
}

const tagItems = computed(() => parseTagList(localForm.value.tags));

function syncTagField(tags: string[]) {
  localForm.value.tags = Array.from(new Set(tags)).join(', ');
}

function commitPendingTags() {
  const pendingTags = parseTagList(localTagInput.value);
  if (pendingTags.length === 0) return;

  syncTagField([...tagItems.value, ...pendingTags]);
  localTagInput.value = '';
}

function removeTag(tag: string) {
  syncTagField(tagItems.value.filter((item) => item !== tag));
}

function handleTagInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault();
    commitPendingTags();
  }
}

watch(
  () => [props.visible, props.initialForm] as const,
  ([visible]) => {
    if (!visible) return;
    localForm.value = { ...props.initialForm };
    selectedFiles.value = [];
    dragOver.value = false;
    localWarning.value = '';
    localTagInput.value = '';
    removeConfirmVisible.value = false;
    pendingRemoveIndex.value = -1;
  },
  { deep: true }
);

const canSubmit = computed(
  () =>
    !!props.selectedSpace && selectedFiles.value.length > 0 && !props.submitting
);

function requestClose() {
  if (props.submitting) return;
  emit('close');
}

function mergeFiles(files: File[]) {
  const merged = [...selectedFiles.value];
  for (const file of files) {
    const exists = merged.some(
      (item) =>
        item.name === file.name &&
        item.size === file.size &&
        item.lastModified === file.lastModified
    );
    if (!exists) {
      merged.push(file);
    }
  }
  selectedFiles.value = merged;
}

function handleFileInput(event: Event) {
  const target = event.target as HTMLInputElement;
  if (!target.files) return;
  mergeFiles(Array.from(target.files));
  target.value = '';
  localWarning.value = '';
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1);
}

function openRemoveFileConfirm(index: number) {
  if (props.submitting || index < 0 || index >= selectedFiles.value.length)
    return;
  pendingRemoveIndex.value = index;
  removeConfirmVisible.value = true;
}

function closeRemoveFileConfirm() {
  if (props.submitting) return;
  removeConfirmVisible.value = false;
  pendingRemoveIndex.value = -1;
}

function confirmRemoveFile() {
  if (pendingRemoveIndex.value < 0) return;
  removeFile(pendingRemoveIndex.value);
  closeRemoveFileConfirm();
}

function handleDragOver(event: DragEvent) {
  if (!props.selectedSpace || props.submitting) return;
  event.preventDefault();
  dragOver.value = true;
}

function handleDragLeave(event: DragEvent) {
  event.preventDefault();
  dragOver.value = false;
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  dragOver.value = false;
  if (!props.selectedSpace || props.submitting) return;
  if (!event.dataTransfer?.files?.length) return;
  mergeFiles(Array.from(event.dataTransfer.files));
  localWarning.value = '';
}

function submitUpload() {
  if (!props.selectedSpace) {
    localWarning.value = '请先在页面中选择一个知识空间。';
    return;
  }

  if (selectedFiles.value.length === 0) {
    localWarning.value = '请先选择至少一个文件。';
    return;
  }

  commitPendingTags();
  emit('submit', {
    files: [...selectedFiles.value],
    tags: localForm.value.tags,
    version_label: localForm.value.version_label
  });
}
</script>

<template>
  <Teleport to="body">
    <Transition name="kb-modal-fade">
      <div v-if="visible" class="kb-modal-backdrop">
        <div class="kb-modal-panel kb-upload-panel">
          <div class="kb-modal-head">
            <div>
              <div class="kb-modal-title">上传文档</div>
              <div class="kb-modal-subtitle">
                {{
                  selectedSpace
                    ? `文档会归入：${selectedSpace.path}`
                    : '请选择知识空间后再打开上传弹窗。'
                }}
              </div>
            </div>
            <button
              type="button"
              class="kb-modal-close"
              :disabled="submitting"
              @click="requestClose">
              <CloseOutlined />
            </button>
          </div>

          <div v-if="selectedSpace" class="kb-upload-space-card">
            <div class="kb-upload-space-path">{{ selectedSpace.path }}</div>
            <div class="kb-upload-space-meta">
              {{ selectedSpace.total_document_count }} 篇文档 ·
              {{ selectedSpace.child_count }} 个子空间
            </div>
          </div>

          <div class="kb-form-grid">
            <label class="kb-field-block">
              <span class="kb-field-label">附加标签</span>
              <div
                class="kb-tag-editor"
                :class="{
                  'kb-tag-editor-disabled': submitting || !selectedSpace
                }">
                <span v-for="tag in tagItems" :key="tag" class="kb-tag-chip">
                  <span>{{ tag }}</span>
                  <button
                    type="button"
                    class="kb-tag-chip-remove"
                    :disabled="submitting || !selectedSpace"
                    @click="removeTag(tag)">
                    <MinusCircleOutlined />
                  </button>
                </span>
                <input
                  v-model="localTagInput"
                  class="kb-tag-input"
                  type="text"
                  placeholder="输入后按回车生成标签"
                  :disabled="submitting || !selectedSpace"
                  @keydown="handleTagInputKeydown"
                  @blur="commitPendingTags" />
              </div>
            </label>

            <label class="kb-field-block">
              <span class="kb-field-label">文档版本</span>
              <input
                v-model="localForm.version_label"
                class="kb-field-input"
                type="text"
                placeholder="可选，留空则继承空间版本"
                :disabled="submitting || !selectedSpace" />
            </label>
          </div>

          <label
            class="kb-upload-zone"
            :class="{
              'kb-upload-zone-active': dragOver,
              'kb-upload-zone-disabled': !selectedSpace || submitting
            }"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop">
            <input
              type="file"
              class="kb-hidden-input"
              multiple
              accept=".pdf,.docx,.txt,.md,.rst,.csv"
              :disabled="!selectedSpace || submitting"
              @change="handleFileInput" />
            <div class="kb-upload-zone-inner">
              <InboxOutlined class="kb-upload-icon" />
              <div class="kb-upload-title">拖入文件，或点击选择文件</div>
              <div class="kb-upload-hint">
                支持 PDF、Word、TXT、Markdown、CSV；上传后会自动建立索引。
              </div>
            </div>
          </label>

          <div v-if="localWarning" class="kb-upload-warning">
            {{ localWarning }}
          </div>

          <div v-if="selectedFiles.length > 0" class="kb-file-list">
            <div class="kb-file-list-head">
              <span>待上传文件</span>
              <span>{{ selectedFiles.length }} 个</span>
            </div>
            <div class="kb-file-items">
              <div
                v-for="(file, index) in selectedFiles"
                :key="`${file.name}-${file.lastModified}-${file.size}`"
                class="kb-file-item">
                <div class="kb-file-copy">
                  <div class="kb-file-name">{{ file.name }}</div>
                  <div class="kb-file-meta">
                    {{ Math.max(file.size / 1024 / 1024, 0.01).toFixed(2) }} MB
                  </div>
                </div>
                <button
                  type="button"
                  class="kb-file-remove"
                  :disabled="submitting"
                  @click="openRemoveFileConfirm(index)">
                  移除
                </button>
              </div>
            </div>
          </div>

          <div class="kb-modal-actions">
            <button
              type="button"
              class="kb-btn kb-btn-secondary"
              :disabled="submitting"
              @click="requestClose">
              取消
            </button>
            <button
              type="button"
              class="kb-btn kb-btn-primary"
              :disabled="!canSubmit"
              @click="submitUpload">
              <LoadingOutlined v-if="submitting" class="spin" />
              <UploadOutlined v-else />
              开始上传
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <KnowledgeDangerConfirmModal
      :visible="removeConfirmVisible"
      :title="
        pendingRemoveFile
          ? `移除待上传文件“${pendingRemoveFile.name}”`
          : '移除待上传文件'
      "
      :message="'该文件会从当前上传队列中移除，不会提交到知识库。'"
      :impact-stats="pendingRemoveStats"
      :impact-items="['当前待上传文件', '本次上传队列顺序']"
      confirm-text="确认移除文件"
      :submitting="submitting"
      @close="closeRemoveFileConfirm"
      @confirm="confirmRemoveFile" />
  </Teleport>
</template>

<style scoped>
.kb-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.kb-modal-panel {
  width: min(760px, 100%);
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(40px) saturate(200%);
  -webkit-backdrop-filter: blur(40px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    0 20px 48px rgba(0, 0, 0, 0.1),
    0 8px 24px rgba(0, 0, 0, 0.05);
}

.kb-upload-panel {
  width: min(720px, 100%);
}

.kb-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.kb-modal-title {
  color: var(--color-heading);
  font-size: 20px;
  font-weight: 700;
}

.kb-modal-subtitle {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.kb-modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.kb-modal-close:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--color-heading);
}

.kb-upload-space-card {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.kb-upload-space-path {
  color: var(--color-success-strong);
  font-size: 15px;
  font-weight: 700;
}

.kb-upload-space-meta {
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.kb-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.kb-field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-field-label {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.kb-field-input {
  width: 100%;
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--color-text);
  padding: 12px 14px;
  font: inherit;
  font-size: 14px;
  line-height: 1.5;
  transition: all 0.2s ease;
}

.kb-field-input:focus {
  outline: none;
  background: #ffffff;
  border-color: rgba(47, 107, 79, 0.4);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.1);
}

.kb-tag-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 48px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  padding: 8px 10px;
  transition: all 0.2s ease;
}

.kb-tag-editor:focus-within {
  background: #ffffff;
  border-color: rgba(47, 107, 79, 0.4);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.1);
}

.kb-tag-editor-disabled {
  opacity: 0.7;
}

.kb-tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(47, 107, 79, 0.1);
  color: var(--color-success-strong);
  font-size: 12px;
  font-weight: 600;
}

.kb-tag-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.kb-tag-input {
  flex: 1 1 180px;
  min-width: 140px;
  min-height: 30px;
  border: none;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: 14px;
  outline: none;
  padding: 0 2px;
}

.kb-tag-input::placeholder {
  color: var(--color-text-muted);
}

.kb-upload-zone {
  position: relative;
  display: block;
  margin-top: 18px;
  border: 1.5px dashed var(--color-border-strong);
  border-radius: 22px;
  background: var(--color-surface);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.kb-upload-zone:hover {
  transform: translateY(-1px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-subtle);
}

.kb-upload-zone-active {
  border-color: var(--color-success);
  background: var(--color-background-soft);
}

.kb-upload-zone-disabled {
  cursor: not-allowed;
  opacity: 0.64;
  transform: none;
  box-shadow: none;
}

.kb-upload-zone-inner {
  padding: 32px 20px;
  text-align: center;
}

.kb-hidden-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: inherit;
}

.kb-upload-icon {
  font-size: 28px;
  color: var(--color-success);
}

.kb-upload-title {
  margin-top: 12px;
  color: var(--color-heading);
  font-size: 16px;
  font-weight: 700;
}

.kb-upload-hint {
  margin-top: 6px;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.kb-upload-warning {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--color-warning-soft);
  border: 1px solid var(--color-warning-border);
  color: var(--color-warning-strong);
  font-size: 13px;
}

.kb-file-list {
  margin-top: 18px;
  border-radius: 18px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.kb-file-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border-soft);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.kb-file-items {
  display: flex;
  flex-direction: column;
}

.kb-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.kb-file-item + .kb-file-item {
  border-top: 1px solid var(--color-border-soft);
}

.kb-file-copy {
  min-width: 0;
}

.kb-file-name {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 600;
  word-break: break-word;
}

.kb-file-meta {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.kb-file-remove {
  border: 0;
  background: transparent;
  color: var(--color-danger);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.kb-modal-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.kb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 20px;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.kb-btn:disabled,
.kb-modal-close:disabled,
.kb-file-remove:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kb-btn-primary {
  background: var(--color-success);
  color: var(--color-on-success);
  box-shadow: 0 4px 12px rgba(47, 107, 79, 0.25);
}

.kb-btn-primary:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(47, 107, 79, 0.35);
}

.kb-btn-primary:not(:disabled):active {
  transform: scale(0.98);
}

.kb-btn-secondary {
  background: rgba(0, 0, 0, 0.04);
  color: var(--color-text);
}

.kb-btn-secondary:not(:disabled):hover {
  background: rgba(0, 0, 0, 0.08);
}

.kb-btn-secondary:not(:disabled):active {
  transform: scale(0.98);
}

.kb-modal-fade-enter-active,
.kb-modal-fade-leave-active {
  transition: opacity 0.22s ease;
}

.kb-modal-fade-enter-from,
.kb-modal-fade-leave-to {
  opacity: 0;
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

@media (max-width: 720px) {
  .kb-modal-backdrop {
    padding: 14px;
  }

  .kb-modal-panel {
    padding: 18px;
    border-radius: 24px;
  }

  .kb-form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .kb-modal-actions {
    flex-direction: column-reverse;
  }

  .kb-btn {
    width: 100%;
  }

  .kb-file-item {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
