<script setup lang="ts">
import { DownOutlined } from '@ant-design/icons-vue';
import { computed } from 'vue';
import { cn } from '@/utils/cn';

export interface OSelectOption {
  label: string;
  value: string | number;
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    options?: OSelectOption[];
    disabled?: boolean;
  }>(),
  {
    modelValue: '',
    options: () => [],
    disabled: false
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const classes = computed(() =>
  cn(
    'group relative flex min-h-10 items-center rounded-lg border border-border bg-white px-3 transition-all duration-200 shadow-sm hover:border-border-strong focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20',
    props.disabled &&
      'cursor-not-allowed bg-surface-muted border-border-soft opacity-70 shadow-none hover:border-border-soft focus-within:ring-0'
  )
);
</script>

<template>
  <div :class="classes">
    <select
      :value="props.modelValue"
      :disabled="props.disabled"
      class="w-full appearance-none border-0 bg-transparent pr-12 text-[14px] font-medium leading-6 text-(--oui-color-text) outline-none"
      @change="
        emit('update:modelValue', ($event.target as HTMLSelectElement).value)
      ">
      <slot>
        <option
          v-for="option in props.options"
          :key="option.value"
          :value="option.value">
          {{ option.label }}
        </option>
      </slot>
    </select>
    <span
      class="pointer-events-none absolute right-3 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-black/6 bg-white/80 text-[11px] text-(--oui-color-text-muted) shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] transition-all duration-200 group-focus-within:border-black/10 group-focus-within:text-(--oui-color-heading)">
      <DownOutlined />
    </span>
  </div>
</template>
