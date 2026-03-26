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
  'group relative flex min-h-10 items-center gap-2 rounded-lg border bg-white px-3 text-sm font-medium transition-all duration-200 outline-none',
  {
    variants: {
      status: {
        default:
          'border-border text-text placeholder:text-subtle shadow-sm hover:border-border-strong focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20',
        error:
          'border-danger-border text-danger shadow-sm focus-within:border-danger focus-within:ring-2 focus-within:ring-danger/20'
      },
      disabled: {
        true: 'cursor-not-allowed bg-surface-muted border-border-soft text-subtle shadow-none hover:border-border-soft opacity-70',
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
