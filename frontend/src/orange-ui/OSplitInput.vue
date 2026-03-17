<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    length?: number;
    disabled?: boolean;
  }>(),
  {
    modelValue: '',
    length: 6,
    disabled: false
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const cells = computed(() =>
  Array.from(
    { length: props.length },
    (_, index) => props.modelValue[index] || ''
  )
);

function focusNext(target: HTMLInputElement) {
  const next = target.nextElementSibling as HTMLInputElement | null;
  next?.focus();
}

function focusPrev(target: HTMLInputElement) {
  const prev = target.previousElementSibling as HTMLInputElement | null;
  prev?.focus();
}

function updateValue(index: number, value: string, target: HTMLInputElement) {
  const chars = props.modelValue.split('');
  chars[index] = value.slice(-1);
  const nextValue = chars.join('').slice(0, props.length);
  emit('update:modelValue', nextValue);
  if (value) {
    focusNext(target);
  }
}

function handleKeydown(index: number, event: KeyboardEvent) {
  const target = event.target as HTMLInputElement;
  if (event.key === 'Backspace' && !target.value && index > 0) {
    focusPrev(target);
  }
}
</script>

<template>
  <div class="flex items-center gap-2">
    <input
      v-for="(cell, index) in cells"
      :key="index"
      :value="cell"
      :disabled="props.disabled"
      maxlength="1"
      class="o-focus-ring h-11 w-10 rounded-(--oui-radius-sm) border border-(--oui-color-border-soft) bg-white text-center text-base font-semibold text-(--oui-color-heading) outline-none shadow-[inset_0_1px_2px_rgba(0,0,0,0.02)] transition-all duration-300 hover:border-(--oui-color-border) focus:border-(--oui-color-border-strong) focus:shadow-[0_0_0_4px_rgba(24,24,27,0.08),inset_0_1px_2px_rgba(0,0,0,0.02)] disabled:opacity-60 disabled:cursor-not-allowed disabled:bg-(--oui-color-surface-soft)"
      @input="
        updateValue(
          index,
          ($event.target as HTMLInputElement).value,
          $event.target as HTMLInputElement
        )
      "
      @keydown="handleKeydown(index, $event)" />
  </div>
</template>
