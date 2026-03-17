<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, useAttrs } from 'vue';
import { cn } from '@/utils/cn';

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

const wrapperClass = computed(() =>
  cn(
    'group relative flex min-h-12 items-center gap-2 rounded-[16px] border border-black/8 bg-linear-to-b from-white to-[rgba(248,248,249,0.96)] px-4 text-[14px] font-medium leading-6 text-(--oui-color-text) transition-all duration-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.88),inset_0_-1px_0_rgba(24,24,27,0.02),0_6px_18px_rgba(24,24,27,0.04)] hover:border-black/12 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.92),inset_0_-1px_0_rgba(24,24,27,0.03),0_10px_24px_rgba(24,24,27,0.06)] focus-within:-translate-y-[1px] focus-within:border-black/18 focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06),inset_0_1px_0_rgba(255,255,255,0.92),0_12px_28px_rgba(24,24,27,0.08)] focus-within:bg-white',
    props.disabled &&
      'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-60 shadow-none hover:border-black/8 hover:shadow-none',
    attrs.class
  )
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
      class="w-full border-0 bg-transparent p-0 text-inherit leading-inherit font-inherit outline-none placeholder:font-normal placeholder:text-(--oui-color-text-subtle)"
      @input="handleInput"
      @blur="emit('blur', $event)"
      @keydown="emit('keydown', $event)" />
    <slot name="suffix" />
  </div>
</template>
