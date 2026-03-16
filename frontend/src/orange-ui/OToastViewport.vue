<script setup lang="ts">
import {
  CheckCircleOutlined,
  CloseOutlined,
  InfoCircleOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';
import type { OToastItem } from './useOToast';

const props = defineProps<{
  items: OToastItem[];
}>();

const emit = defineEmits<{
  remove: [id: number];
}>();

function iconForTone(tone: OToastItem['tone']) {
  if (tone === 'success') return CheckCircleOutlined;
  if (tone === 'error' || tone === 'warning') return WarningOutlined;
  return InfoCircleOutlined;
}
</script>

<template>
  <Teleport to="body">
    <div
      class="pointer-events-none fixed inset-x-0 top-6 z-10000 flex justify-center px-4">
      <TransitionGroup
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="translate-y-2 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="translate-y-0 opacity-100"
        leave-to-class="translate-y-2 opacity-0"
        tag="div"
        class="flex w-full max-w-xl flex-col gap-3">
        <div
          v-for="item in props.items"
          :key="item.id"
          :class="[
            'pointer-events-auto flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-floating backdrop-blur-xl',
            item.tone === 'success' &&
              'border-(--oui-color-success-border) bg-[rgba(238,247,241,0.96)] text-(--oui-color-success)',
            item.tone === 'error' &&
              'border-(--oui-color-danger-border) bg-[rgba(254,242,242,0.98)] text-(--oui-color-danger)',
            item.tone === 'warning' &&
              'border-(--oui-color-warning-border) bg-[rgba(255,247,237,0.98)] text-(--oui-color-warning)',
            item.tone === 'info' &&
              'border-(--oui-color-border-soft) bg-[rgba(255,255,255,0.96)] text-(--oui-color-text-secondary)'
          ]">
          <component :is="iconForTone(item.tone)" class="mt-0.5 text-base" />
          <div class="min-w-0 flex-1">
            <div
              v-if="item.title"
              class="text-sm font-semibold text-(--oui-color-heading)">
              {{ item.title }}
            </div>
            <div class="text-sm leading-6 text-current">
              {{ item.message }}
            </div>
          </div>
          <button
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-full text-current/70 transition hover:bg-black/5 hover:text-current"
            @click="emit('remove', item.id)">
            <CloseOutlined />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
