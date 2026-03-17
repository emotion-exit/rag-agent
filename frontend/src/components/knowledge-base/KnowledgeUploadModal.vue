<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { InboxOutlined } from '@ant-design/icons-vue';
import KnowledgeDangerConfirmModal from '@/components/knowledge-base/KnowledgeDangerConfirmModal.vue';
import type {
  KnowledgeSpace,
  UploadForm,
  UploadSubmitPayload
} from '@/types/knowledgeBase';
import {
  OAlert,
  OCard,
  OFormItem,
  OInput,
  OModal,
  OPanelRow,
  OTagInput
} from '@/orange-ui';

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

watch(
  () => [props.visible, props.initialForm] as const,
  ([visible]) => {
    if (!visible) return;
    localForm.value = { ...props.initialForm };
    selectedFiles.value = [];
    dragOver.value = false;
    localWarning.value = '';
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
  if (props.submitting || index < 0 || index >= selectedFiles.value.length) {
    return;
  }
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

  emit('submit', {
    files: [...selectedFiles.value],
    tags: localForm.value.tags,
    version_label: localForm.value.version_label
  });
}
</script>

<template>
  <OModal
    :visible="visible"
    title="上传文档"
    :subtitle="
      selectedSpace
        ? `文档会归入：${selectedSpace.path}`
        : '请选择知识空间后再打开上传弹窗。'
    "
    :closable="!submitting"
    cancel-text="取消"
    :cancel-disabled="submitting"
    confirm-text="开始上传"
    :confirm-loading="submitting"
    :confirm-disabled="!canSubmit"
    width="min(720px, 100%)"
    @confirm="submitUpload"
    @close="requestClose">
    <div class="space-y-4.5">
      <OCard v-if="selectedSpace" padding="sm" tone="muted">
        <div class="text-sm font-semibold text-(--oui-color-heading)">
          {{ selectedSpace.path }}
        </div>
        <div class="mt-1 text-xs leading-5 text-(--oui-color-text-muted)">
          {{ selectedSpace.total_document_count }} 篇文档 ·
          {{ selectedSpace.child_count }} 个子空间
        </div>
      </OCard>

      <div class="grid grid-cols-2 gap-3.5 max-md:grid-cols-1">
        <OFormItem label="附加标签">
          <OTagInput
            v-model="localForm.tags"
            :disabled="submitting || !selectedSpace" />
        </OFormItem>
        <OFormItem label="文档版本">
          <OInput
            v-model="localForm.version_label"
            :disabled="submitting || !selectedSpace"
            placeholder="可选，留空则继承空间版本" />
        </OFormItem>
      </div>

      <label
        :class="[
          'relative flex cursor-pointer flex-col items-center justify-center rounded-(--oui-radius-lg) border-2 border-dashed px-6 py-8 text-center transition-all duration-300',
          dragOver
            ? 'border-(--oui-color-primary) bg-(--oui-color-primary-soft) shadow-[inset_0_1px_0_rgba(255,255,255,0.6),0_4px_12px_rgba(24,24,27,0.08)]'
            : 'border-(--oui-color-border) bg-white hover:border-(--oui-color-border-strong) hover:bg-(--oui-color-surface-soft)',
          (!selectedSpace || submitting) &&
            'cursor-not-allowed opacity-60 hover:border-(--oui-color-border) hover:bg-white'
        ]"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop">
        <input
          type="file"
          class="absolute inset-0 cursor-pointer opacity-0"
          multiple
          accept=".pdf,.docx,.txt,.md,.rst,.csv"
          :disabled="!selectedSpace || submitting"
          @change="handleFileInput" />
        <InboxOutlined class="text-3xl text-(--oui-color-text-muted)" />
        <div class="mt-3 text-base font-semibold text-(--oui-color-heading)">
          拖入文件，或点击选择文件
        </div>
        <div class="mt-1 text-sm leading-6 text-(--oui-color-text-muted)">
          支持 PDF、Word、TXT、Markdown、CSV；上传后会自动建立索引。
        </div>
      </label>

      <OAlert v-if="localWarning" tone="warning">{{ localWarning }}</OAlert>

      <OCard v-if="selectedFiles.length > 0" padding="sm">
        <div
          class="flex items-center justify-between text-sm font-semibold text-(--oui-color-heading)">
          <span>待上传文件</span>
          <span class="text-(--oui-color-text-muted)">
            {{ selectedFiles.length }} 个
          </span>
        </div>
        <div class="mt-3 space-y-2">
          <OPanelRow
            v-for="(file, index) in selectedFiles"
            :key="`${file.name}-${file.lastModified}-${file.size}`">
            <div class="min-w-0">
              <div
                class="truncate text-sm font-medium text-(--oui-color-heading)">
                {{ file.name }}
              </div>
              <div class="text-xs leading-5 text-(--oui-color-text-muted)">
                {{ Math.max(file.size / 1024 / 1024, 0.01).toFixed(2) }} MB
              </div>
            </div>
            <OButton
              variant="ghost"
              size="sm"
              :disabled="submitting"
              @click="openRemoveFileConfirm(index)">
              移除
            </OButton>
          </OPanelRow>
        </div>
      </OCard>
    </div>
  </OModal>

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
</template>
