<script setup lang="ts">
import {
  CheckCircleOutlined,
  InfoCircleOutlined,
  WarningOutlined
} from '@ant-design/icons-vue';

const props = withDefaults(
  defineProps<{
    tone?: 'success' | 'error' | 'warning' | 'info';
    title?: string;
  }>(),
  {
    tone: 'info',
    title: ''
  }
);

function iconForTone(tone: string) {
  if (tone === 'success') return CheckCircleOutlined;
  if (tone === 'warning' || tone === 'error') return WarningOutlined;
  return InfoCircleOutlined;
}
</script>

<template>
  <div
    :class="[
      'relative overflow-hidden grid grid-cols-[auto_minmax(0,1fr)] gap-3.5 rounded-[18px] border px-4.5 py-4.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_8px_24px_rgba(24,24,27,0.04)]',
      props.tone === 'success' &&
        'border-(--oui-color-success-border) bg-linear-to-b from-[rgba(244,251,247,0.98)] to-[rgba(238,247,241,0.9)]',
      props.tone === 'warning' &&
        'border-(--oui-color-warning-border) bg-linear-to-b from-[rgba(255,250,244,0.98)] to-[rgba(255,247,237,0.9)]',
      props.tone === 'error' &&
        'border-(--oui-color-danger-border) bg-linear-to-b from-[rgba(255,246,246,0.98)] to-[rgba(254,242,242,0.9)]',
      props.tone === 'info' &&
        'border-(--oui-color-border-soft) bg-linear-to-b from-white to-[rgba(248,248,248,0.92)]'
    ]">
    <span
      :class="[
        'pointer-events-none absolute top-3 bottom-3 left-3 w-1 rounded-full opacity-80',
        props.tone === 'success' && 'bg-(--oui-color-success)',
        props.tone === 'warning' && 'bg-(--oui-color-warning)',
        props.tone === 'error' && 'bg-(--oui-color-danger)',
        props.tone === 'info' && 'bg-(--oui-color-text-subtle)'
      ]" />
    <component
      :is="iconForTone(props.tone)"
      :class="[
        'relative mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-xl border text-[15px] shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]',
        props.tone === 'success' &&
          'border-(--oui-color-success-border) bg-white/70 text-(--oui-color-success)',
        props.tone === 'warning' &&
          'border-(--oui-color-warning-border) bg-white/70 text-(--oui-color-warning)',
        props.tone === 'error' &&
          'border-(--oui-color-danger-border) bg-white/70 text-(--oui-color-danger)',
        props.tone === 'info' &&
          'border-(--oui-color-border-soft) bg-white/80 text-(--oui-color-text-secondary)'
      ]" />
    <div class="relative min-w-0 pl-1.5">
      <div
        v-if="props.title"
        class="text-[14px] font-semibold leading-relaxed text-(--oui-color-heading)">
        {{ props.title }}
      </div>
      <div
        :class="[
          'leading-relaxed text-(--oui-color-text-secondary)',
          props.title ? 'mt-1 text-[13px]' : 'text-sm'
        ]">
        <slot />
      </div>
    </div>
  </div>
</template>
