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
    <div class="space-y-3 flex flex-col gap-3">
      <div v-if="impactStats.length > 0" class="grid grid-cols-2 gap-2.5">
        <OCard
          v-for="item in impactStats"
          :key="item.label"
          tone="danger"
          padding="none"
          :class="[
            'flex flex-col justify-center px-3.5 py-2.5 border border-[#fcb5b5]/30 rounded-xl! shadow-none bg-[#fef2f2]!'
          ]">
          <div
            :class="[
              item.kind === 'context'
                ? 'text-[13px] font-semibold leading-[1.4] text-(--oui-color-heading) line-clamp-1'
                : 'text-[18px] font-bold leading-none text-(--oui-color-danger)'
            ]">
            {{ item.value }}
          </div>
          <div :class="['mt-1 text-[11px] font-medium text-[#b1372a]/70']">
            {{ item.label }}
          </div>
        </OCard>
      </div>

      <OCard
        v-if="impactItems.length > 0"
        tone="danger"
        padding="none"
        class="border border-[#fcb5b5]/30 rounded-xl! px-4 py-3 shadow-none bg-[#fef2f2]!">
        <div class="text-[12px] font-bold leading-5 text-(--oui-color-danger)">
          此操作会删除以下数据：
        </div>
        <ul
          class="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] leading-[1.6] text-(--oui-color-danger)/80">
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
          class="min-w-35 bg-[#b1372a]! text-white! border-[#b1372a]! shadow-md hover:bg-[#9c2f24]!"
          @click="requestConfirm">
          {{ submitting ? '处理中...' : confirmText }}
        </OButton>
      </div>
    </template>
  </OModal>
</template>
