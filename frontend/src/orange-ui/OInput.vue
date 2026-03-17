<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, useAttrs } from 'vue';
import { cn } from '@/utils/cn';
import { cva, type VariantProps } from 'class-variance-authority';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    type?: 'text' | 'password' | 'number';
    placeholder?: string;
    disabled?: boolean;
    min?: number | string;
    max?: number | string;
    step?: number | string;
    class?: any;
  }>(),
  {
    modelValue: '',
    type: 'text',
    placeholder: '',
    disabled: false,
    min: undefined,
    max: undefined,
    step: undefined
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string | number];
  blur: [event: FocusEvent];
  keydown: [event: KeyboardEvent];
  input: [event: Event];
}>();

const inputVariants = cva(
  'group relative flex min-h-12 items-center gap-2 rounded-2xl border bg-white px-4 text-[14px] font-medium leading-6 transition-all duration-300',
  {
    variants: {
      status: {
        default:
          'border-black/8 text-body shadow-[inset_0_1px_0_rgba(255,255,255,0.88),inset_0_-1px_0_rgba(24,24,27,0.02),0_4px_12px_rgba(24,24,27,0.03)] hover:border-black/15 hover:shadow-[0_6px_16px_rgba(24,24,27,0.05)] focus-within:border-brand-soft focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.04),inset_0_1px_0_rgba(255,255,255,0.92),0_8px_20px_rgba(24,24,27,0.08)]',
        error:
          'border-danger-border text-danger shadow-sm focus-within:border-danger focus-within:ring-4 focus-within:ring-danger/20'
      },
      disabled: {
        true: 'cursor-not-allowed bg-surface-muted border-black/5 text-subtle shadow-none hover:border-black/5 hover:shadow-none opacity-80',
        false: ''
      }
    },
    defaultVariants: {
      status: 'default',
      disabled: false
    }
  }
);

const wrapperClass = computed(() =>
  cn(inputVariants({ disabled: props.disabled }), props.class)
);

const rootAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement;
  emit(
    'update:modelValue',
    props.type === 'number' ? target.valueAsNumber || 0 : target.value
  );
  emit('input', event);
}
</script>

<template>
  <div v-bind="rootAttrs" :class="wrapperClass">
    <slot name="prefix" />
    <input
      :value="props.modelValue"
      :type="props.type"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :min="props.min"
      :max="props.max"
      :step="props.step"
      class="w-full border-0 bg-transparent p-0 text-inherit leading-inherit font-inherit outline-none placeholder:font-normal placeholder:text-subtle disabled:cursor-not-allowed"
      @input="handleInput"
      @blur="emit('blur', $event)"
      @keydown="emit('keydown', $event)" />
    <slot name="suffix" />
  </div>
</template>
