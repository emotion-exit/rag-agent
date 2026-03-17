<script setup lang="ts">
import { OCard, OModal } from '@/orange-ui';

defineOptions({
  name: 'KnowledgeDangerConfirmModal'
});

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title: string;
    message: string;
    impactItems?: string[];
    impactStats?: Array<{ label: string; value: string }>;
    confirmText?: string;
    cancelText?: string;
    submitting?: boolean;
  }>(),
  {
    impactItems: () => [],
    impactStats: () => [],
    confirmText: '确认操作',
    cancelText: '取消',
    submitting: false
  }
);

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();

function requestClose() {
  if (props.submitting) return;
  emit('close');
}

function requestConfirm() {
  if (props.submitting) return;
  emit('confirm');
}
</script>

<template>
  <OModal
    :visible="visible"
    :title="title"
    :subtitle="message"
    :closable="!submitting"
    :cancel-text="cancelText"
    :cancel-disabled="submitting"
    :confirm-text="submitting ? '处理中...' : confirmText"
    confirm-variant="danger"
    :confirm-loading="submitting"
    width="min(540px, 100%)"
    @confirm="requestConfirm"
    @close="requestClose">
    <div class="space-y-4">
      <div
        v-if="impactStats.length > 0"
        class="grid grid-cols-[repeat(auto-fit,minmax(110px,1fr))] gap-2.5">
        <OCard
          v-for="item in impactStats"
          :key="item.label"
          tone="danger"
          padding="sm"
          class="min-h-22">
          <div class="text-lg font-bold leading-5 text-(--oui-color-danger)">
            {{ item.value }}
          </div>
          <div class="mt-1.5 text-xs leading-5 text-(--oui-color-text-muted)">
            {{ item.label }}
          </div>
        </OCard>
      </div>

      <OCard v-if="impactItems.length > 0" tone="danger" padding="sm">
        <div class="text-sm font-bold text-(--oui-color-danger)">
          此操作会同时影响
        </div>
        <ul
          class="mt-2 list-disc space-y-1 pl-4 text-sm leading-6 text-(--oui-color-text-secondary)">
          <li v-for="item in impactItems" :key="item">{{ item }}</li>
        </ul>
      </OCard>
    </div>
  </OModal>
</template>
