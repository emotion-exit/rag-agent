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
    class?: any;
  }>(),
  {
    padding: 'md',
    tone: 'default',
    interactive: false
  }
);

const classes = computed(() =>
  cn(
    'rounded-xl border border-border bg-white shadow-sm transition-all duration-200 ease-out',
    props.padding === 'none' && 'p-0',
    props.padding === 'sm' && 'p-4',
    props.padding === 'md' && 'p-6',
    props.padding === 'lg' && 'p-8',
    props.tone === 'default' && 'bg-white',
    props.tone === 'muted' && 'bg-surface-muted border-border-soft',
    props.tone === 'success' && 'bg-success-soft border-success-border',
    props.tone === 'warning' && 'bg-warning-soft border-warning-border',
    props.tone === 'danger' && 'bg-danger-soft border-danger-border',
    props.interactive &&
      'hover:shadow-md hover:border-border-strong cursor-pointer active:scale-[0.99]',
    props.class
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
