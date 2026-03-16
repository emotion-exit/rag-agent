<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    padding?: 'none' | 'sm' | 'md' | 'lg';
    tone?: 'default' | 'muted' | 'success' | 'warning' | 'danger';
    interactive?: boolean;
    htmlClass?: string;
  }>(),
  {
    padding: 'md',
    tone: 'default',
    interactive: false,
    htmlClass: ''
  }
);

const classes = computed(() =>
  cn(
    'rounded-[18px] border shadow-[inset_0_1px_0_rgba(255,255,255,0.85),0_12px_30px_rgba(24,24,27,0.04)]',
    props.padding === 'none' && 'p-0',
    props.padding === 'sm' && 'p-4',
    props.padding === 'md' && 'p-5',
    props.padding === 'lg' && 'p-6',
    props.tone === 'default' &&
      'border-black/7 bg-linear-to-b from-[#fcfcfd] to-[#f7f7f8]',
    props.tone === 'muted' &&
      'border-black/5 bg-linear-to-b from-[#f8f8f8] to-[#f3f3f3]',
    props.tone === 'success' &&
      'border-(--oui-color-success-border) bg-linear-to-b from-[#f4fbf7] to-[#eef7f1]',
    props.tone === 'warning' &&
      'border-(--oui-color-warning-border) bg-linear-to-b from-[#fffaf4] to-[#fff7ed]',
    props.tone === 'danger' &&
      'border-(--oui-color-danger-border) bg-linear-to-b from-[#fff6f6] to-[#fef2f2]',
    props.interactive &&
      'transition-all duration-300 hover:-translate-y-1 hover:shadow-floating cursor-pointer',
    props.htmlClass
  )
);
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
