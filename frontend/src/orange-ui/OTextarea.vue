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
    'w-full text-[14px] font-medium leading-6 text-(--oui-color-text)',
    props.appearance === 'default' &&
      'group rounded-[16px] border border-black/8 bg-linear-to-b from-white to-[rgba(248,248,249,0.96)] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.88),inset_0_-1px_0_rgba(24,24,27,0.02),0_6px_18px_rgba(24,24,27,0.04)] transition-all duration-300 hover:border-black/12 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.92),inset_0_-1px_0_rgba(24,24,27,0.03),0_10px_24px_rgba(24,24,27,0.06)] focus-within:-translate-y-[1px] focus-within:border-black/18 focus-within:shadow-[0_0_0_4px_rgba(24,24,27,0.06),inset_0_1px_0_rgba(255,255,255,0.92),0_12px_28px_rgba(24,24,27,0.08)]',
    props.appearance === 'plain' && 'bg-transparent p-0 shadow-none',
    props.disabled &&
      (props.appearance === 'default'
        ? 'cursor-not-allowed bg-(--oui-color-surface-soft) opacity-60 shadow-none hover:border-black/8 hover:shadow-none'
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
