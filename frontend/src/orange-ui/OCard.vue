<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, useAttrs } from 'vue';
import { cn } from '@/utils/cn';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    padding?: 'none' | 'sm' | 'md' | 'lg';
    tone?: 'default' | 'muted' | 'success' | 'warning' | 'danger';
    interactive?: boolean;
  }>(),
  {
    padding: 'md',
    tone: 'default',
    interactive: false
  }
);

const classes = computed(() =>
  cn(
    'rounded-[20px] border shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_12px_30px_rgba(24,24,27,0.04)] backdrop-blur-sm will-change-transform transition-[transform,box-shadow,border-color,background-color] duration-300 ease-out',
    props.padding === 'none' && 'p-0',
    props.padding === 'sm' && 'p-4',
    props.padding === 'md' && 'p-5',
    props.padding === 'lg' && 'p-6',
    props.tone === 'default' &&
      'border-black/[0.08] bg-linear-to-b from-[rgba(253,253,253,0.98)] to-[rgba(248,248,249,0.95)]',
    props.tone === 'muted' &&
      'border-black/[0.06] bg-linear-to-b from-[rgba(249,249,249,0.95)] to-[rgba(244,244,244,0.92)]',
    props.tone === 'success' &&
      'border-(--oui-color-success-border) bg-linear-to-b from-[rgba(244,251,247,0.95)] to-[rgba(238,247,241,0.92)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8),0_12px_30px_rgba(47,107,79,0.06)]',
    props.tone === 'warning' &&
      'border-(--oui-color-warning-border) bg-linear-to-b from-[rgba(255,250,244,0.95)] to-[rgba(255,247,237,0.92)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8),0_12px_30px_rgba(217,119,6,0.06)]',
    props.tone === 'danger' &&
      'border-(--oui-color-danger-border) bg-linear-to-b from-[rgba(255,246,246,0.95)] to-[rgba(254,242,242,0.92)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8),0_12px_30px_rgba(177,55,42,0.06)]',
    props.interactive &&
      'hover:-translate-y-1.5 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_20px_48px_rgba(24,24,27,0.12)] cursor-pointer active:translate-y-0 active:shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_12px_30px_rgba(24,24,27,0.04)]',
    attrs.class
  )
);

const rootAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});
</script>

<template>
  <div v-bind="rootAttrs" :class="classes">
    <slot />
  </div>
</template>
