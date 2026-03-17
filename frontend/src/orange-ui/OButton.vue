<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, useAttrs } from 'vue';
import { LoadingOutlined } from '@ant-design/icons-vue';
import { cn } from '@/utils/cn';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset';
    variant?: 'primary' | 'secondary' | 'danger' | 'warning' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    block?: boolean;
  }>(),
  {
    type: 'button',
    variant: 'primary',
    size: 'md',
    disabled: false,
    loading: false,
    block: false
  }
);

const classes = computed(() =>
  cn(
    'o-focus-ring inline-flex items-center justify-center gap-2 rounded-[var(--oui-radius-full)] border font-medium transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.97] will-change-transform',
    props.size === 'sm' && 'min-h-9 px-3.5 text-sm',
    props.size === 'md' && 'min-h-10 px-4 text-[14px]',
    props.size === 'lg' && 'min-h-11 px-5 text-[15px]',
    props.block && 'w-full',
    props.variant === 'primary' &&
      'border-[var(--oui-color-primary)] bg-[var(--oui-color-primary)] text-[var(--oui-color-on-primary)] shadow-[0_1px_0_rgba(255,255,255,0.4)_inset,0_8px_20px_rgba(24,24,27,0.08)] hover:bg-[var(--oui-color-primary-strong)] hover:border-[var(--oui-color-primary-strong)] hover:shadow-[0_1px_0_rgba(255,255,255,0.4)_inset,0_12px_30px_rgba(24,24,27,0.12)] hover:-translate-y-0.5',
    props.variant === 'secondary' &&
      'border-[var(--oui-color-border)] bg-white text-[var(--oui-color-heading)] shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_8px_20px_rgba(24,24,27,0.06)] hover:bg-[var(--oui-color-surface-soft)] hover:shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_12px_24px_rgba(24,24,27,0.08)] hover:-translate-y-0.5',
    props.variant === 'danger' &&
      'border-[var(--oui-color-danger)] bg-[var(--oui-color-danger)] text-white shadow-[0_1px_0_rgba(255,255,255,0.3)_inset,0_8px_20px_rgba(177,55,42,0.18)] hover:brightness-95 hover:shadow-[0_1px_0_rgba(255,255,255,0.3)_inset,0_12px_24px_rgba(177,55,42,0.25)] hover:-translate-y-0.5',
    props.variant === 'warning' &&
      'border-[var(--oui-color-warning-border)] bg-[var(--oui-color-warning-soft)] text-[var(--oui-color-warning)] shadow-[0_8px_20px_rgba(217,119,6,0.08)] hover:bg-[rgba(255,237,213,0.95)] hover:shadow-[0_12px_24px_rgba(217,119,6,0.12)] hover:-translate-y-0.5',
    props.variant === 'ghost' &&
      'border-transparent bg-transparent text-[var(--oui-color-text-secondary)] hover:bg-black/4 hover:text-[var(--oui-color-heading)]',
    attrs.class
  )
);

const buttonAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});
</script>

<template>
  <button
    v-bind="buttonAttrs"
    :type="props.type"
    :disabled="props.disabled || props.loading"
    :class="classes">
    <LoadingOutlined v-if="props.loading" class="animate-spin" />
    <slot />
  </button>
</template>
