<script setup lang="ts">
import { computed } from 'vue';
import { LoadingOutlined } from '@ant-design/icons-vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset';
    variant?: 'primary' | 'secondary' | 'danger' | 'warning' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    block?: boolean;
    htmlClass?: string;
  }>(),
  {
    type: 'button',
    variant: 'primary',
    size: 'md',
    disabled: false,
    loading: false,
    block: false,
    htmlClass: ''
  }
);

const classes = computed(() =>
  cn(
    'o-focus-ring inline-flex items-center justify-center gap-2 rounded-(--oui-radius-full) border font-medium transition duration-200 disabled:cursor-not-allowed disabled:opacity-60',
    props.size === 'sm' && 'min-h-9 px-3.5 text-sm',
    props.size === 'md' && 'min-h-10 px-4 text-[14px]',
    props.size === 'lg' && 'min-h-11 px-5 text-[15px]',
    props.block && 'w-full',
    props.variant === 'primary' &&
      'border-(--oui-color-primary) bg-(--oui-color-primary) text-(--oui-color-on-primary) shadow-subtle hover:bg-(--oui-color-primary-strong) hover:border-(--oui-color-primary-strong)',
    props.variant === 'secondary' &&
      'border-(--oui-color-border) bg-(--oui-color-surface) text-(--oui-color-heading) hover:bg-(--oui-color-surface-soft)',
    props.variant === 'danger' &&
      'border-(--oui-color-danger) bg-(--oui-color-danger) text-white hover:brightness-95',
    props.variant === 'warning' &&
      'border-(--oui-color-warning-border) bg-(--oui-color-warning-soft) text-(--oui-color-warning) hover:bg-[rgba(255,237,213,0.95)]',
    props.variant === 'ghost' &&
      'border-transparent bg-transparent text-(--oui-color-text-secondary) hover:bg-black/5 hover:text-(--oui-color-heading)',
    props.htmlClass
  )
);
</script>

<template>
  <button
    :type="props.type"
    :disabled="props.disabled || props.loading"
    :class="classes">
    <LoadingOutlined v-if="props.loading" class="animate-spin" />
    <slot />
  </button>
</template>
