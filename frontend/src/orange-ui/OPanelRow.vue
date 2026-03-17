<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    interactive?: boolean;
  }>(),
  {
    interactive: true
  }
);

const classes = computed(() =>
  cn(
    'flex items-center justify-between gap-3 rounded-(--oui-radius-md) border border-(--oui-color-border-soft) bg-white px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
    props.interactive &&
      'transition-all duration-200 hover:border-(--oui-color-border) hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.6),0_2px_8px_rgba(24,24,27,0.04)]'
  )
);
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
