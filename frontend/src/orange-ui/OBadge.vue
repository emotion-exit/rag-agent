<script setup lang="ts">
import { computed } from 'vue';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/cn';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-surface-soft text-body border border-border-soft',
        primary:
          'bg-brand text-brand-foreground border border-brand/20 shadow-sm',
        success: 'bg-success/15 text-success-strong border border-success/30',
        warning: 'bg-warning/15 text-warning-strong border border-warning/30',
        danger: 'bg-danger/15 text-danger-strong border border-danger/30',
        outline: 'text-body border border-border'
      },
      size: {
        sm: 'px-2 py-0.5 text-[11px]',
        md: 'px-2.5 py-1 text-xs',
        lg: 'px-3 py-1 text-sm'
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'md'
    }
  }
);

type BadgeProps = VariantProps<typeof badgeVariants>;

const props = withDefaults(
  defineProps<{
    variant?: NonNullable<BadgeProps['variant']>;
    size?: NonNullable<BadgeProps['size']>;
    dot?: boolean;
    class?: string;
  }>(),
  {
    variant: 'default',
    size: 'md',
    dot: false
  }
);

const classes = computed(() =>
  cn(badgeVariants({ variant: props.variant, size: props.size }), props.class)
);
</script>

<template>
  <span :class="classes">
    <span v-if="dot" class="relative flex h-2 w-2">
      <span
        class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 bg-current"></span>
      <span
        class="relative inline-flex h-1.5 w-1.5 rounded-full bg-current m-auto"></span>
    </span>
    <slot />
  </span>
</template>
