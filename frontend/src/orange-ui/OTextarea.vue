<script setup lang="ts">
defineOptions({
  inheritAttrs: false
});

import { computed, ref, useAttrs } from 'vue';
import { cn } from '@/utils/cn';

const attrs = useAttrs();

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    placeholder?: string;
    rows?: number;
    disabled?: boolean;
    resize?: 'none' | 'vertical' | 'auto';
    appearance?: 'default' | 'plain';
    class?: any;
  }>(),
  {
    modelValue: '',
    placeholder: '',
    rows: 4,
    disabled: false,
    resize: 'vertical',
    appearance: 'default'
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
  blur: [event: FocusEvent];
  input: [event: Event];
  keydown: [event: KeyboardEvent];
}>();

const textareaEl = ref<HTMLTextAreaElement | null>(null);

const wrapperClass = computed(() =>
  cn(
    'w-full text-sm font-medium leading-6 text-text',
    props.appearance === 'default' &&
      'group rounded-lg border border-border bg-white px-3 py-2 shadow-sm transition-all duration-200 hover:border-border-strong focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20',
    props.appearance === 'plain' && 'bg-transparent p-0 shadow-none',
    props.disabled &&
      (props.appearance === 'default'
        ? 'cursor-not-allowed bg-surface-muted border-border-soft opacity-70 shadow-none hover:border-border-soft focus-within:ring-0'
        : 'cursor-not-allowed opacity-60'),
    props.class
  )
);

const textareaClasses = computed(() =>
  cn(
    'w-full min-h-[inherit] max-h-[inherit] border-0 bg-transparent p-0 text-inherit leading-inherit font-inherit outline-none placeholder:font-normal placeholder:text-(--oui-color-text-subtle)',
    props.resize === 'none' && 'resize-none',
    props.resize === 'vertical' && 'resize-y',
    props.resize === 'auto' && 'resize'
  )
);

function handleInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value);
  emit('input', event);
}

const rootAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});

defineExpose({
  textareaEl,
  focus() {
    textareaEl.value?.focus();
  }
});
</script>

<template>
  <div v-bind="rootAttrs" :class="wrapperClass">
    <textarea
      ref="textareaEl"
      :value="props.modelValue"
      :rows="props.rows"
      :disabled="props.disabled"
      :placeholder="props.placeholder"
      :class="textareaClasses"
      @input="handleInput"
      @blur="emit('blur', $event)"
      @keydown="emit('keydown', $event)" />
  </div>
</template>
