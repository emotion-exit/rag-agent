<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { WarningOutlined } from '@ant-design/icons-vue';
import KnowledgeDangerConfirmModal from '@/components/knowledge-base/KnowledgeDangerConfirmModal.vue';
import type { DocumentInfo, KnowledgeSpace } from '@/types/knowledgeBase';
import {
  OAlert,
  OButton,
  OCard,
  OFormItem,
  OModal,
  OSelect
} from '@/orange-ui';

defineOptions({
  name: 'UngroupedMigrationModal'
});

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  spaces: KnowledgeSpace[];
  ungroupedDocuments: DocumentInfo[];
}>();

const emit = defineEmits<{
  close: [];
  submit: [targetSpaceId: string];
}>();

const targetSpaceId = ref('');
const localWarning = ref('');
const confirmVisible = ref(false);

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    targetSpaceId.value = '';
    localWarning.value = '';
    confirmVisible.value = false;
  }
);

const previewDocuments = computed(() => props.ungroupedDocuments.slice(0, 5));
const hiddenCount = computed(() =>
  Math.max(props.ungroupedDocuments.length - previewDocuments.value.length, 0)
);
const estimatedChunkCount = computed(() =>
  props.ungroupedDocuments.reduce(
    (total, doc) => total + Number(doc.chunk_count || 0),
    0
  )
);
const selectedSpace = computed(
  () =>
    props.spaces.find((item) => item.space_id === targetSpaceId.value) || null
);
const confirmImpactStats = computed(() => [
  {
    label: '待迁移文档',
    value: `${props.ungroupedDocuments.length} 篇`
  },
  {
    label: '预计重建分块',
    value: `${estimatedChunkCount.value} 个`
  },
  {
    label: '目标空间',
    value: selectedSpace.value ? selectedSpace.value.path : '尚未选择'
  }
]);
const confirmImpactItems = computed(() => {
  const previewNames = previewDocuments.value.map(
    (doc) => `文档：${doc.filename}`
  );
  const effects = [
    '文档分类、主题、标签会改写为目标空间信息',
    '相关文本分块会重新建立向量索引'
  ];

  if (hiddenCount.value > 0) {
    previewNames.push(`其余 ${hiddenCount.value} 篇文档也会一并迁移`);
  }

  return [...effects, ...previewNames];
});

const spaceOptions = computed(() => [
  { label: '请选择目标知识空间', value: '' },
  ...props.spaces.map((item) => ({
    label: item.path,
    value: item.space_id
  }))
]);

function requestClose() {
  if (props.submitting || confirmVisible.value) return;
  emit('close');
}

function closeConfirm() {
  if (props.submitting) return;
  confirmVisible.value = false;
}

function submitMigration() {
  if (!targetSpaceId.value) {
    localWarning.value = '请先选择迁移目标知识空间。';
    return;
  }

  localWarning.value = '';
  confirmVisible.value = true;
}

function confirmMigration() {
  if (!targetSpaceId.value) {
    localWarning.value = '请先选择迁移目标知识空间。';
    confirmVisible.value = false;
    return;
  }

  emit('submit', targetSpaceId.value);
}
</script>

<template>
  <OModal
    :visible="visible"
    title="迁移未归类文档"
    subtitle="将历史未归类文档统一迁移到正式知识空间，并重建对应索引。"
    :closable="!submitting"
    width="min(720px, 100%)"
    @close="requestClose">
    <div class="space-y-4.5">
      <OAlert tone="warning" title="此操作会重新 embedding">
        系统会把目标空间的分类、主题、标签和路径重新写入文档，并为受影响文本块重新建立向量索引。迁移期间这些文档会短暂重建检索结果。
      </OAlert>

      <div class="grid grid-cols-3 gap-3 max-md:grid-cols-1">
        <OCard padding="sm">
          <div class="text-xs text-(--oui-color-text-muted)">待迁移文档</div>
          <div class="mt-1.5 text-lg font-bold text-(--oui-color-heading)">
            {{ ungroupedDocuments.length }} 篇
          </div>
        </OCard>
        <OCard padding="sm">
          <div class="text-xs text-(--oui-color-text-muted)">预计重建分块</div>
          <div class="mt-1.5 text-lg font-bold text-(--oui-color-heading)">
            {{ estimatedChunkCount }} 个
          </div>
          <div class="mt-1 text-xs leading-5 text-(--oui-color-text-muted)">
            基于当前分块数预估，实际重建后可能略有变化
          </div>
        </OCard>
        <OCard padding="sm">
          <div class="text-xs text-(--oui-color-text-muted)">目标空间</div>
          <div
            class="mt-1.5 text-sm font-semibold leading-6 text-(--oui-color-heading)">
            {{ selectedSpace ? selectedSpace.path : '尚未选择' }}
          </div>
        </OCard>
      </div>

      <OFormItem label="迁移到">
        <OSelect
          v-model="targetSpaceId"
          :options="spaceOptions"
          :disabled="submitting || spaces.length === 0" />
      </OFormItem>

      <OCard padding="sm">
        <div class="text-sm font-semibold text-(--oui-color-heading)">
          本次会处理的文档
        </div>
        <div class="mt-3 space-y-2">
          <div
            v-for="doc in previewDocuments"
            :key="doc.doc_id"
            class="flex items-center justify-between gap-3 rounded-(--oui-radius-md) border border-(--oui-color-border-soft) px-4 py-3">
            <div
              class="min-w-0 truncate text-sm font-medium text-(--oui-color-heading)">
              {{ doc.filename }}
            </div>
            <div
              class="shrink-0 text-xs leading-5 text-(--oui-color-text-muted)">
              {{ doc.chunk_count }} 个分块
            </div>
          </div>
          <div
            v-if="hiddenCount > 0"
            class="text-sm leading-6 text-(--oui-color-text-muted)">
            其余 {{ hiddenCount }} 篇文档也会一起迁移
          </div>
        </div>
      </OCard>

      <OAlert v-if="localWarning" tone="warning">{{ localWarning }}</OAlert>
    </div>

    <template #footer>
      <OButton variant="secondary" :disabled="submitting" @click="requestClose">
        取消
      </OButton>
      <OButton
        variant="danger"
        :loading="submitting"
        :disabled="submitting || !targetSpaceId"
        @click="submitMigration">
        <WarningOutlined v-if="!submitting" />
        继续确认迁移
      </OButton>
    </template>
  </OModal>

  <KnowledgeDangerConfirmModal
    :visible="confirmVisible"
    :title="
      selectedSpace ? `迁移到“${selectedSpace.name}”` : '确认迁移未归类文档'
    "
    :message="'确认后系统会把未归类文档迁入目标空间，并重新写入空间元数据与检索索引。'"
    :impact-stats="confirmImpactStats"
    :impact-items="confirmImpactItems"
    confirm-text="开始迁移并重建索引"
    :submitting="submitting"
    @close="closeConfirm"
    @confirm="confirmMigration" />
</template>
