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
  'o-focus-ring inline-flex items-center justify-center gap-2 rounded-full border border-transparent font-medium transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.97] will-change-transform outline-none focus-visible:ring-4 focus-visible:ring-black/8',
  {
    variants: {
      variant: {
        primary:
          'bg-brand text-brand-foreground shadow-[0_1px_0_rgba(255,255,255,0.4)_inset,0_8px_20px_rgba(24,24,27,0.08)] hover:bg-brand-strong hover:shadow-[0_1px_0_rgba(255,255,255,0.4)_inset,0_12px_30px_rgba(24,24,27,0.12)] hover:-translate-y-0.5',
        secondary:
          'border-border bg-white text-heading shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_8px_20px_rgba(24,24,27,0.06)] hover:bg-surface-soft hover:shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_12px_24px_rgba(24,24,27,0.08)] hover:-translate-y-0.5 relative after:absolute after:inset-0 after:rounded-full after:shadow-[0_0_0_1px_rgba(0,0,0,0.05)] after:pointer-events-none',
        danger:
          'bg-danger text-white shadow-[0_1px_0_rgba(255,255,255,0.3)_inset,0_8px_20px_rgba(177,55,42,0.18)] hover:brightness-95 hover:shadow-[0_1px_0_rgba(255,255,255,0.3)_inset,0_12px_24px_rgba(177,55,42,0.25)] hover:-translate-y-0.5',
        warning:
          'border-warning-border bg-warning-soft text-warning shadow-[0_8px_20px_rgba(217,119,6,0.08)] hover:bg-[rgba(255,237,213,0.95)] hover:shadow-[0_12px_24px_rgba(217,119,6,0.12)] hover:-translate-y-0.5',
        ghost:
          'bg-transparent text-secondary hover:bg-black/4 hover:text-heading shadow-none active:bg-black/5'
      },
      size: {
        sm: 'min-h-9 px-3.5 text-sm',
        md: 'min-h-10 px-4 text-[14px]',
        lg: 'min-h-11 px-5 text-[15px]'
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
