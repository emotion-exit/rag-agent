<script setup lang="ts">
import { OButton, OCard, OModal } from '@/orange-ui';

defineOptions({
  name: 'KnowledgeDangerConfirmModal'
});

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title: string;
    message: string;
    impactItems?: string[];
    impactStats?: Array<{
      label: string;
      value: string;
      kind?: 'metric' | 'context';
    }>;
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
    <div class="space-y-3.5">
      <div
        v-if="impactStats.length > 0"
        class="grid grid-cols-[repeat(auto-fit,minmax(145px,1fr))] gap-2.5">
        <OCard
          v-for="item in impactStats"
          :key="item.label"
          tone="danger"
          padding="sm"
          :class="[
            'flex min-h-22 flex-col justify-between border-transparent! rounded-2xl! shadow-[0_2px_8px_rgba(177,55,42,0.08),0_1px_2px_rgba(177,55,42,0.04)]!',
            item.kind === 'context'
              ? 'bg-[linear-gradient(135deg,rgba(255,252,252,0.98),rgba(254,249,249,0.96))]!'
              : 'bg-[linear-gradient(180deg,rgba(255,254,254,0.98),rgba(255,251,251,0.96))]!'
          ]">
          <div
            :class="[
              item.kind === 'context'
                ? 'text-[15px] font-semibold leading-[1.4] text-(--oui-color-heading) line-clamp-2'
                : 'text-[26px] font-bold leading-none tracking-[-0.02em] text-(--oui-color-danger)'
            ]">
            {{ item.value }}
          </div>
          <div
            :class="[
              'mt-1.5 text-[11px] font-medium leading-[1.4] tracking-wide',
              item.kind === 'context'
                ? 'text-(--oui-color-text-muted) opacity-75'
                : 'text-(--oui-color-text-muted)'
            ]">
            {{ item.label }}
          </div>
        </OCard>
      </div>

      <OCard
        v-if="impactItems.length > 0"
        tone="danger"
        padding="sm"
        class="border-transparent! rounded-2xl! shadow-[0_2px_8px_rgba(177,55,42,0.08),0_1px_2px_rgba(177,55,42,0.04)]! bg-[linear-gradient(180deg,rgba(255,254,254,0.98),rgba(255,251,251,0.96))]!">
        <div class="text-[13px] font-bold leading-5 text-(--oui-color-danger)">
          此操作会同时影响
        </div>
        <ul
          class="mt-2 list-disc space-y-0.5 pl-4 text-[13px] leading-[1.7] text-(--oui-color-text-secondary)">
          <li v-for="item in impactItems" :key="item">{{ item }}</li>
        </ul>
      </OCard>
    </div>

    <template #footer>
      <div
        class="flex w-full flex-col-reverse gap-2.5 sm:flex-row sm:justify-end">
        <OButton
          variant="ghost"
          size="md"
          :disabled="submitting"
          class="min-w-25"
          @click="requestClose">
          {{ cancelText }}
        </OButton>
        <OButton
          variant="danger"
          size="md"
          :loading="submitting"
          :disabled="submitting"
          class="min-w-35 bg-[#b1372a]! text-white! border-[#b1372a]! shadow-[0_8px_20px_rgba(177,55,42,0.24),0_2px_6px_rgba(177,55,42,0.12)]! hover:bg-[#9c2f24]!"
          @click="requestConfirm">
          {{ submitting ? '处理中...' : confirmText }}
        </OButton>
      </div>
    </template>
  </OModal>
</template>
