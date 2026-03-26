<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, useAttrs } from 'vue';
import { LoadingOutlined } from '@ant-design/icons-vue';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const attrs = useAttrs();

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98] outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-black',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-on-primary shadow-sm hover:bg-primary-strong',
        secondary:
          'border border-border bg-white text-heading shadow-sm hover:bg-surface-soft hover:border-border-strong',
        danger: 'bg-danger text-white shadow-sm hover:brightness-90',
        warning:
          'border border-warning-border bg-warning text-white shadow-sm hover:brightness-90',
        ghost:
          'bg-transparent text-secondary hover:bg-surface-muted hover:text-heading active:bg-black/5'
      },
      size: {
        sm: 'min-h-8 px-3 text-xs',
        md: 'min-h-10 px-4 text-sm',
        lg: 'min-h-12 px-6 text-base'
      },
      block: {
        true: 'w-full',
        false: ''
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
      block: false
    }
  }
);

type ButtonProps = VariantProps<typeof buttonVariants>;

const props = withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset';
    variant?: NonNullable<ButtonProps['variant']>;
    size?: NonNullable<ButtonProps['size']>;
    disabled?: boolean;
    loading?: boolean;
    block?: boolean;
    class?: any;
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
    buttonVariants({
      variant: props.variant,
      size: props.size,
      block: props.block
    }),
    props.class
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
