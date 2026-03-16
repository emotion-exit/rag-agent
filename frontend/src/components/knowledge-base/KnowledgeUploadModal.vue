<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  CloseOutlined,
  InboxOutlined,
  LoadingOutlined,
  UploadOutlined
} from '@ant-design/icons-vue';
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

watch(
  () => [props.visible, props.initialForm] as const,
  ([visible]) => {
    if (!visible) return;
    localForm.value = { ...props.initialForm };
    selectedFiles.value = [];
    dragOver.value = false;
    localWarning.value = '';
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
      <div v-if="visible" class="kb-modal-backdrop" @click.self="requestClose">
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
              <input
                v-model="localForm.tags"
                class="kb-field-input"
                type="text"
                placeholder="可选，多个标签用逗号分隔"
                :disabled="submitting || !selectedSpace" />
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
                  @click="removeFile(index)">
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
  </Teleport>
</template>

<style scoped>
.kb-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 180;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(24, 24, 27, 0.16);
  backdrop-filter: blur(8px);
}

.kb-modal-panel {
  width: min(760px, 100%);
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 24px;
  border-radius: 28px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-floating);
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
  width: 38px;
  height: 38px;
  border: 1px solid var(--color-border-soft);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
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
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  color: var(--color-text);
  padding: 12px 14px;
  font: inherit;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.kb-field-input:focus {
  outline: none;
  border-color: var(--color-success);
  box-shadow: 0 0 0 3px rgba(47, 107, 79, 0.1);
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
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
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
  border-color: var(--color-success);
}

.kb-btn-secondary {
  background: var(--color-surface);
  color: var(--color-text);
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
