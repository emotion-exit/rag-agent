<script setup lang="ts">
import { computed } from 'vue';
import { cn } from '@/utils/cn';

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    type?: 'text' | 'password' | 'number';
    placeholder?: string;
    disabled?: boolean;
    min?: number | string;
    max?: number | string;
    step?: number | string;
    htmlClass?: string;
    inputClass?: string;
  }>(),
  {
    modelValue: '',
    type: 'text',
    placeholder: '',
    disabled: false,
    min: undefined,
    max: undefined,
    step: undefined,
    htmlClass: '',
    inputClass: ''
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
    'flex min-h-11 items-center gap-2 rounded-(--oui-radius-md) border border-(--oui-color-border-soft) bg-(--oui-color-surface) px-4 transition duration-200 focus-within:border-(--oui-color-border-strong) focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06)]',
    props.disabled &&
      'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-70',
    props.htmlClass
  )
);

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
  <div :class="wrapperClass">
    <slot name="prefix" />
    <input
      :value="props.modelValue"
      :type="props.type"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :min="props.min"
      :max="props.max"
      :step="props.step"
      :class="[
        'w-full border-0 bg-transparent p-0 text-[14px] leading-6 text-(--oui-color-text) outline-none placeholder:text-(--oui-color-text-subtle)',
        props.inputClass
      ]"
      @input="handleInput"
      @blur="emit('blur', $event)"
      @keydown="emit('keydown', $event)" />
    <slot name="suffix" />
  </div>
</template>
